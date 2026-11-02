from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Absence, Assignment, Employee, ServicePlan, Shift, Substitution, TimeEntry, User
from app.schemas.common import (
    AbsenceOut,
    AssignShiftIn,
    AssignmentOut,
    EmployeeOut,
    GenerateShiftsIn,
    PlanningWeekOut,
    ServicePlanCreate,
    ServicePlanOut,
    ShiftOut,
    StableAssigneeIn,
    SubstituteIn,
    SubstitutionOut,
    TimeEntryOut,
)
from app.services.assignments import (
    AssignmentError,
    OverlapError,
    assign_employee_to_shift,
    set_stable_plan_assignee,
    substitute_on_shift,
)
from app.services.shifts import generate_shifts_for_week, planning_week

router = APIRouter(tags=["planeamento"])


@router.get("/service-plans", response_model=list[ServicePlanOut])
def list_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ServicePlan]:
    return list(
        db.scalars(select(ServicePlan).where(ServicePlan.organization_id == user.organization_id).order_by(ServicePlan.name))
    )


@router.post("/service-plans", response_model=ServicePlanOut, status_code=201)
def create_plan(
    payload: ServicePlanCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServicePlan:
    plan = ServicePlan(
        organization_id=user.organization_id,
        contract_line_id=payload.contract_line_id,
        name=payload.name,
        recurrence_rule=payload.recurrence_rule,
        default_employee_id=payload.default_employee_id,
        active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/service-plans/{plan_id}/stable-assignee", response_model=ServicePlanOut)
def patch_stable_assignee(
    plan_id: uuid.UUID,
    payload: StableAssigneeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServicePlan:
    plan = db.scalar(
        select(ServicePlan).where(
            ServicePlan.id == plan_id,
            ServicePlan.organization_id == user.organization_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plano de serviço não encontrado")
    try:
        return set_stable_plan_assignee(
            db,
            organization_id=user.organization_id,
            service_plan=plan,
            employee_id=payload.default_employee_id,
        )
    except AssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/shifts/generate", response_model=list[ShiftOut])
def generate_shifts(
    payload: GenerateShiftsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShiftOut]:
    plan = db.scalar(
        select(ServicePlan).where(
            ServicePlan.id == payload.service_plan_id,
            ServicePlan.organization_id == user.organization_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plano de serviço não encontrado")
    shifts = generate_shifts_for_week(
        db,
        organization_id=user.organization_id,
        service_plan=plan,
        week_start=payload.week_start,
        author_user_id=user.id,
    )
    week = planning_week(db, organization_id=user.organization_id, week_start=payload.week_start)
    created_ids = {s.id for s in shifts}
    return [_shift_out(s) for s in week if s.id in created_ids]


@router.get("/planning/week", response_model=PlanningWeekOut)
def get_planning_week(
    week_start: date = Query(..., description="Segunda-feira da semana (ISO)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanningWeekOut:
    shifts = planning_week(db, organization_id=user.organization_id, week_start=week_start)
    employees = list(
        db.scalars(
            select(Employee)
            .where(Employee.organization_id == user.organization_id, Employee.status == "ATIVO")
            .order_by(Employee.full_name)
        )
    )
    week_end = week_start + timedelta(days=6)
    absences = list(
        db.scalars(
            select(Absence)
            .options(joinedload(Absence.employee))
            .where(
                Absence.organization_id == user.organization_id,
                Absence.start_date <= week_end,
                Absence.end_date >= week_start,
            )
        ).unique()
    )
    unassigned = sum(1 for s in shifts if not any(a.active for a in s.assignments))
    return PlanningWeekOut(
        week_start=week_start,
        week_end=week_end,
        shifts=[_shift_out(s) for s in shifts],
        employees=[EmployeeOut.model_validate(e) for e in employees],
        absences=[
            AbsenceOut(
                id=a.id,
                organization_id=a.organization_id,
                employee_id=a.employee_id,
                employee_name=a.employee.full_name if a.employee else None,
                absence_type=a.absence_type,
                start_date=a.start_date,
                end_date=a.end_date,
                status=a.status,
                reason=a.reason,
            )
            for a in absences
        ],
        unassigned_count=unassigned,
    )


@router.post("/shifts/{shift_id}/assign", response_model=ShiftOut)
def assign_shift(
    shift_id: uuid.UUID,
    payload: AssignShiftIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftOut:
    shift = _get_shift(db, user.organization_id, shift_id)
    try:
        assign_employee_to_shift(
            db,
            organization_id=user.organization_id,
            shift=shift,
            employee_id=payload.employee_id,
            author_user_id=user.id,
            allow_overlap_override=payload.allow_overlap_override,
            set_as_stable_default=payload.set_as_stable_default,
        )
    except OverlapError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "conflicting_shift_ids": [str(i) for i in exc.conflicting_shift_ids],
            },
        ) from exc
    except AssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    shift = _get_shift(db, user.organization_id, shift_id)
    return _shift_out(shift)


@router.post("/shifts/{shift_id}/substitute", response_model=SubstitutionOut)
def substitute_shift(
    shift_id: uuid.UUID,
    payload: SubstituteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubstitutionOut:
    shift = _get_shift(db, user.organization_id, shift_id)
    try:
        sub = substitute_on_shift(
            db,
            organization_id=user.organization_id,
            shift=shift,
            substitute_employee_id=payload.substitute_employee_id,
            reason=payload.reason,
            absence_id=payload.absence_id,
            author_user_id=user.id,
            allow_overlap_override=payload.allow_overlap_override,
        )
    except OverlapError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "conflicting_shift_ids": [str(i) for i in exc.conflicting_shift_ids],
            },
        ) from exc
    except AssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sub = db.scalar(
        select(Substitution)
        .options(
            joinedload(Substitution.planned_employee),
            joinedload(Substitution.executed_employee),
        )
        .where(Substitution.id == sub.id)
    )
    assert sub is not None
    return SubstitutionOut(
        id=sub.id,
        shift_id=sub.shift_id,
        planned_employee_id=sub.planned_employee_id,
        executed_employee_id=sub.executed_employee_id,
        planned_employee_name=sub.planned_employee.full_name if sub.planned_employee else None,
        executed_employee_name=sub.executed_employee.full_name if sub.executed_employee else None,
        reason=sub.reason,
        absence_id=sub.absence_id,
        created_at=sub.created_at,
    )


@router.get("/shifts/{shift_id}/time-entry", response_model=TimeEntryOut)
def get_time_entry(
    shift_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntry:
    entry = db.scalar(
        select(TimeEntry).where(TimeEntry.shift_id == shift_id, TimeEntry.organization_id == user.organization_id)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Registo de horas não encontrado")
    return entry


def _get_shift(db: Session, organization_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
    shift = db.scalar(
        select(Shift)
        .options(
            joinedload(Shift.assignments).joinedload(Assignment.employee),
            joinedload(Shift.store),
        )
        .where(Shift.id == shift_id, Shift.organization_id == organization_id)
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Turno não encontrado")
    return shift


def _shift_out(shift) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        organization_id=shift.organization_id,
        contract_line_id=shift.contract_line_id,
        service_plan_id=shift.service_plan_id,
        store_id=shift.store_id,
        store_name=shift.store.name if shift.store else None,
        planned_start=shift.planned_start,
        planned_end=shift.planned_end,
        status=shift.status,
        shift_type=shift.shift_type,
        assignments=[
            AssignmentOut(
                id=a.id,
                employee_id=a.employee_id,
                employee_name=a.employee.full_name if a.employee else None,
                is_substitute=a.is_substitute,
                active=a.active,
            )
            for a in shift.assignments
            if a.active
        ],
    )
