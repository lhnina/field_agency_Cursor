from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Employee, ServicePlan, TimeEntry, User
from app.schemas.common import (
    AssignmentOut,
    EmployeeOut,
    GenerateShiftsIn,
    PlanningWeekOut,
    ServicePlanCreate,
    ServicePlanOut,
    ShiftOut,
    TimeEntryOut,
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
    # reload week view mapping
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
    return PlanningWeekOut(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        shifts=[_shift_out(s) for s in shifts],
        employees=[EmployeeOut.model_validate(e) for e in employees],
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
