"""Assignment, overlap, and substitution domain services (Q04 / Q30)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import AbsenceStatus, HourConcept, ShiftStatus
from app.models import (
    Absence,
    Assignment,
    Employee,
    ServicePlan,
    Shift,
    Substitution,
    TimeEntry,
    TimeStateHistory,
    User,
)
from app.services.docs_gate import DocsSoftBlockError, expired_docs_for_employee, org_soft_block_docs
from app.services.notifications import notify_substitution
from app.services.audit import write_audit


class OverlapError(Exception):
    def __init__(self, message: str, conflicting_shift_ids: list[uuid.UUID]):
        super().__init__(message)
        self.conflicting_shift_ids = conflicting_shift_ids


class AssignmentError(Exception):
    pass


def find_overlapping_shifts(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_id: uuid.UUID,
    planned_start: datetime,
    planned_end: datetime,
    exclude_shift_id: uuid.UUID | None = None,
) -> list[Shift]:
    """Active assignments overlapping the interval for the same collaborator (hard rule)."""
    q = (
        select(Shift)
        .join(Assignment, Assignment.shift_id == Shift.id)
        .where(
            Shift.organization_id == organization_id,
            Assignment.organization_id == organization_id,
            Assignment.employee_id == employee_id,
            Assignment.active.is_(True),
            Shift.status != ShiftStatus.CANCELADO,
            Shift.planned_start < planned_end,
            Shift.planned_end > planned_start,
        )
    )
    if exclude_shift_id:
        q = q.where(Shift.id != exclude_shift_id)
    return list(db.scalars(q).unique())


def employee_has_approved_absence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_id: uuid.UUID,
    on_day: date,
) -> Absence | None:
    return db.scalar(
        select(Absence).where(
            Absence.organization_id == organization_id,
            Absence.employee_id == employee_id,
            Absence.status == AbsenceStatus.APROVADO,
            Absence.start_date <= on_day,
            Absence.end_date >= on_day,
        )
    )


def _hours_between(start: datetime, end: datetime) -> Decimal:
    return Decimal(str((end - start).total_seconds() / 3600))


def _sync_assigned_hours(
    db: Session,
    *,
    organization_id: uuid.UUID,
    shift: Shift,
    assigned: bool,
    author_user_id: uuid.UUID | None,
) -> None:
    entry = db.scalar(select(TimeEntry).where(TimeEntry.shift_id == shift.id))
    if not entry:
        return
    hours = _hours_between(shift.planned_start, shift.planned_end) if assigned else Decimal("0")
    entry.hours_assigned = hours
    db.add(
        TimeStateHistory(
            organization_id=organization_id,
            time_entry_id=entry.id,
            concept=HourConcept.AFETADAS,
            hours=hours,
            reason="Atualização de afetação",
            author_user_id=author_user_id,
        )
    )


def assign_employee_to_shift(
    db: Session,
    *,
    organization_id: uuid.UUID,
    shift: Shift,
    employee_id: uuid.UUID,
    author_user_id: uuid.UUID | None = None,
    allow_overlap_override: bool = False,
    set_as_stable_default: bool = False,
) -> Assignment:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.organization_id == organization_id)
    )
    if not employee:
        raise AssignmentError("Colaborador não encontrado")

    day = shift.planned_start.date()
    absence = employee_has_approved_absence(
        db, organization_id=organization_id, employee_id=employee_id, on_day=day
    )
    if absence:
        raise AssignmentError(
            f"Colaborador em ausência aprovada ({absence.absence_type}) em {day.isoformat()}"
        )

    if org_soft_block_docs(db, organization_id):
        expired = expired_docs_for_employee(
            db, organization_id=organization_id, employee_id=employee_id, on_day=day
        )
        if expired:
            raise DocsSoftBlockError(
                "Documentos expirados — soft-block ativo (REC-07)",
                [d.id for d in expired],
            )

    overlaps = find_overlapping_shifts(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        planned_start=shift.planned_start,
        planned_end=shift.planned_end,
        exclude_shift_id=shift.id,
    )
    if overlaps and not allow_overlap_override:
        raise OverlapError(
            "Sobreposição de turnos ativos para o colaborador",
            [s.id for s in overlaps],
        )

    # Deactivate current active assignments on this shift
    for existing in list(shift.assignments):
        if existing.active:
            existing.active = False

    assignment = Assignment(
        organization_id=organization_id,
        shift_id=shift.id,
        employee_id=employee_id,
        role="EXECUTOR",
        is_substitute=False,
        active=True,
    )
    db.add(assignment)
    shift.status = ShiftStatus.ATRIBUIDO

    if set_as_stable_default and shift.service_plan_id:
        plan = db.get(ServicePlan, shift.service_plan_id)
        if plan and plan.organization_id == organization_id:
            plan.default_employee_id = employee_id

    db.flush()
    _sync_assigned_hours(
        db,
        organization_id=organization_id,
        shift=shift,
        assigned=True,
        author_user_id=author_user_id,
    )
    write_audit(
        db,
        organization_id=organization_id,
        actor_user_id=author_user_id,
        action="SHIFT_ASSIGN",
        entity_type="shift",
        entity_id=shift.id,
        after={"employee_id": str(employee_id), "assignment_id": str(assignment.id)},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def substitute_on_shift(
    db: Session,
    *,
    organization_id: uuid.UUID,
    shift: Shift,
    substitute_employee_id: uuid.UUID,
    reason: str | None = None,
    absence_id: uuid.UUID | None = None,
    author_user_id: uuid.UUID | None = None,
    allow_overlap_override: bool = False,
) -> Substitution:
    """Replace planned assignee with substitute; keep planned vs executed history."""
    active = next((a for a in shift.assignments if a.active), None)
    if not active:
        raise AssignmentError("Turno sem afetação ativa para substituir")

    planned_employee_id = active.employee_id
    if planned_employee_id == substitute_employee_id:
        raise AssignmentError("Substituto igual ao colaborador previsto")

    # Absence check + overlap for substitute
    day = shift.planned_start.date()
    absence = employee_has_approved_absence(
        db,
        organization_id=organization_id,
        employee_id=substitute_employee_id,
        on_day=day,
    )
    if absence:
        raise AssignmentError("Substituto em ausência aprovada neste dia")

    if org_soft_block_docs(db, organization_id):
        expired = expired_docs_for_employee(
            db, organization_id=organization_id, employee_id=substitute_employee_id, on_day=day
        )
        if expired:
            raise DocsSoftBlockError(
                "Substituto com documentos expirados — soft-block ativo (REC-07)",
                [d.id for d in expired],
            )

    overlaps = find_overlapping_shifts(
        db,
        organization_id=organization_id,
        employee_id=substitute_employee_id,
        planned_start=shift.planned_start,
        planned_end=shift.planned_end,
        exclude_shift_id=shift.id,
    )
    if overlaps and not allow_overlap_override:
        raise OverlapError(
            "Substituto com sobreposição de turnos",
            [s.id for s in overlaps],
        )

    active.active = False
    new_asg = Assignment(
        organization_id=organization_id,
        shift_id=shift.id,
        employee_id=substitute_employee_id,
        role="EXECUTOR",
        is_substitute=True,
        replaces_assignment_id=active.id,
        active=True,
    )
    db.add(new_asg)
    db.flush()

    sub = Substitution(
        organization_id=organization_id,
        shift_id=shift.id,
        planned_employee_id=planned_employee_id,
        executed_employee_id=substitute_employee_id,
        original_assignment_id=active.id,
        new_assignment_id=new_asg.id,
        reason=reason or "Substituição operacional",
        absence_id=absence_id,
        created_by_user_id=author_user_id,
    )
    db.add(sub)
    shift.status = ShiftStatus.ATRIBUIDO
    _sync_assigned_hours(
        db,
        organization_id=organization_id,
        shift=shift,
        assigned=True,
        author_user_id=author_user_id,
    )
    db.flush()

    planned_emp = db.get(Employee, planned_employee_id)
    exec_emp = db.get(Employee, substitute_employee_id)
    store_name = shift.store.name if shift.store else "loja"
    # Notify planned collaborator user if linked; always queue email stub when email known
    to_user = None
    if planned_emp and planned_emp.email:
        to_user = db.scalar(select(User).where(User.email == planned_emp.email))
    notify_substitution(
        db,
        organization_id=organization_id,
        to_email=planned_emp.email if planned_emp else None,
        to_user_id=to_user.id if to_user else author_user_id,
        planned_name=planned_emp.full_name if planned_emp else str(planned_employee_id),
        executed_name=exec_emp.full_name if exec_emp else str(substitute_employee_id),
        store_name=store_name,
        substitution_id=sub.id,
    )
    write_audit(
        db,
        organization_id=organization_id,
        actor_user_id=author_user_id,
        action="SHIFT_SUBSTITUTE",
        entity_type="substitution",
        entity_id=sub.id,
        after={
            "planned": str(planned_employee_id),
            "executed": str(substitute_employee_id),
            "shift_id": str(shift.id),
        },
    )
    db.commit()
    db.refresh(sub)
    return sub


def set_stable_plan_assignee(
    db: Session,
    *,
    organization_id: uuid.UUID,
    service_plan: ServicePlan,
    employee_id: uuid.UUID | None,
) -> ServicePlan:
    if employee_id is not None:
        emp = db.scalar(
            select(Employee).where(Employee.id == employee_id, Employee.organization_id == organization_id)
        )
        if not emp:
            raise AssignmentError("Colaborador não encontrado")
    service_plan.default_employee_id = employee_id
    db.commit()
    db.refresh(service_plan)
    return service_plan


def unassigned_shifts_in_range(
    db: Session,
    *,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[Shift]:
    shifts = list(
        db.scalars(
            select(Shift)
            .options(joinedload(Shift.assignments), joinedload(Shift.store))
            .where(
                Shift.organization_id == organization_id,
                Shift.planned_start >= start,
                Shift.planned_start < end,
                Shift.status != ShiftStatus.CANCELADO,
            )
        ).unique()
    )
    return [s for s in shifts if not any(a.active for a in s.assignments)]
