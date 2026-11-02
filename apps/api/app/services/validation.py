"""Time entry validation + Q12 auto-approve + Q23 tacit acceptance stub."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import HourConcept, RoleCode, ShiftStatus, TimeEntryStatus
from app.models import Assignment, Employee, Organization, Shift, TimeEntry, TimeStateHistory, User
from app.services.audit import write_audit

EUR2 = Decimal("0.01")


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(EUR2, rounding=ROUND_HALF_UP)


def add_business_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _history(
    db: Session,
    *,
    organization_id: uuid.UUID,
    entry: TimeEntry,
    concept: str,
    hours: Decimal,
    reason: str,
    author_user_id: uuid.UUID | None,
) -> None:
    db.add(
        TimeStateHistory(
            organization_id=organization_id,
            time_entry_id=entry.id,
            concept=concept,
            hours=hours,
            reason=reason,
            author_user_id=author_user_id,
        )
    )


def compute_billable_payable(
    entry: TimeEntry,
    *,
    approved: Decimal,
    allow_extra: bool,
    engagement_type: str | None,
    rv_hourly: bool = False,
) -> tuple[Decimal, Decimal]:
    """Q11: billable capped at contracted unless manual extra; payable from approved."""
    contracted = Decimal(str(entry.hours_contracted or 0))
    if allow_extra:
        billable = approved
    else:
        billable = min(approved, contracted) if contracted > 0 else approved
    payable = approved  # remuneration basis; RV uses hours * rate at export (Q14)
    return money(billable), money(payable)


class ValidationError(Exception):
    pass


def submit_execution(
    db: Session,
    *,
    organization_id: uuid.UUID,
    entry: TimeEntry,
    hours_executed: Decimal | None = None,
    author_user_id: uuid.UUID | None = None,
    apply_tacit: bool = False,
) -> TimeEntry:
    shift = entry.shift or db.get(Shift, entry.shift_id)
    if not shift:
        raise ValidationError("Turno não encontrado")

    executed = money(hours_executed if hours_executed is not None else entry.hours_assigned or entry.hours_planned)
    entry.hours_executed = executed
    entry.status = TimeEntryStatus.SUBMETIDO
    entry.submitted_at = datetime.now(timezone.utc)
    entry.auto_approved = False
    shift.status = ShiftStatus.PENDENTE_VALIDACAO

    if apply_tacit:
        org = db.get(Organization, organization_id)
        cutoff_hour = 18
        if org and isinstance(org.settings, dict):
            cutoff_hour = int(org.settings.get("tacit_acceptance_cutoff_hour", 18))
        # Q23: tacit acceptance if now is after cutoff on the day before the shift
        day_before = shift.planned_start.date() - timedelta(days=1)
        cutoff = datetime.combine(day_before, time(cutoff_hour, 0), tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= cutoff:
            entry.tacit_accepted = True

    _history(
        db,
        organization_id=organization_id,
        entry=entry,
        concept=HourConcept.EXECUTADAS,
        hours=executed,
        reason="Submissão de execução",
        author_user_id=author_user_id,
    )
    db.commit()
    db.refresh(entry)
    return entry


def supervisor_team_employee_ids(db: Session, user: User) -> set[uuid.UUID] | None:
    """If user is SUPERVISOR (and not admin/gestor), return IDs of their team; else None = no scope limit."""
    codes = {ur.role.code for ur in user.roles}
    if RoleCode.ADMINISTRADOR in codes or RoleCode.GESTOR_OPERACIONAL in codes or RoleCode.DIRECAO in codes:
        return None
    if RoleCode.SUPERVISOR not in codes:
        return None
    if not user.employee_id:
        # Supervisor user without employee link — empty team
        return set()
    team = list(
        db.scalars(
            select(Employee.id).where(
                Employee.organization_id == user.organization_id,
                Employee.supervisor_id == user.employee_id,
            )
        )
    )
    team_ids = set(team)
    team_ids.add(user.employee_id)
    return team_ids


def assert_supervisor_can_validate(db: Session, user: User, shift: Shift) -> None:
    scope = supervisor_team_employee_ids(db, user)
    if scope is None:
        return
    active = next((a for a in shift.assignments if a.active), None)
    if not active or active.employee_id not in scope:
        raise ValidationError("Supervisor só pode validar a sua equipa")


def validate_entry(
    db: Session,
    *,
    organization_id: uuid.UUID,
    entry: TimeEntry,
    action: str,
    hours_approved: Decimal | None = None,
    allow_extra_billable: bool = False,
    adjustment_note: str | None = None,
    author_user_id: uuid.UUID | None = None,
    author_user: User | None = None,
    auto: bool = False,
) -> TimeEntry:
    shift = (
        db.scalar(
            select(Shift)
            .options(joinedload(Shift.assignments).joinedload(Assignment.employee))
            .where(Shift.id == entry.shift_id)
        )
        or entry.shift
    )
    if not shift:
        raise ValidationError("Turno não encontrado")

    if author_user and not auto:
        assert_supervisor_can_validate(db, author_user, shift)

    if action == "REJEITAR":
        entry.status = TimeEntryStatus.REJEITADO
        entry.adjustment_note = adjustment_note
        shift.status = ShiftStatus.REJEITADO
        write_audit(
            db,
            organization_id=organization_id,
            actor_user_id=author_user_id,
            action="HOURS_REJECT",
            entity_type="time_entry",
            entity_id=entry.id,
            after={"status": entry.status},
        )
        db.commit()
        db.refresh(entry)
        return entry

    if action not in {"APROVAR", "AJUSTAR"}:
        raise ValidationError("Ação inválida")

    approved = money(
        hours_approved
        if hours_approved is not None
        else entry.hours_executed or entry.hours_assigned or entry.hours_planned
    )
    engagement = None
    active = next((a for a in shift.assignments if a.active), None)
    if active and active.employee:
        engagement = active.employee.engagement_type

    billable, payable = compute_billable_payable(
        entry,
        approved=approved,
        allow_extra=allow_extra_billable,
        engagement_type=engagement,
    )
    entry.hours_approved = approved
    entry.hours_billable = billable
    entry.hours_payable = payable
    entry.allow_extra_billable = allow_extra_billable
    entry.adjustment_note = adjustment_note
    entry.status = TimeEntryStatus.APROVADO
    entry.approved_at = datetime.now(timezone.utc)
    entry.auto_approved = auto
    shift.status = ShiftStatus.VALIDADO

    for concept, hours, reason in (
        (HourConcept.APROVADAS, approved, "Validação supervisor" if not auto else "Auto-aprovação Q12"),
        (HourConcept.FATURAVEIS, billable, "Cálculo faturável Q11"),
        (HourConcept.REMUNERAVEIS, payable, "Cálculo remunerável"),
    ):
        _history(
            db,
            organization_id=organization_id,
            entry=entry,
            concept=concept,
            hours=hours,
            reason=reason,
            author_user_id=author_user_id,
        )

    write_audit(
        db,
        organization_id=organization_id,
        actor_user_id=author_user_id,
        action="HOURS_APPROVE" if not auto else "HOURS_AUTO_APPROVE",
        entity_type="time_entry",
        entity_id=entry.id,
        after={
            "status": entry.status,
            "hours_approved": str(approved),
            "hours_billable": str(billable),
            "allow_extra": allow_extra_billable,
        },
    )
    db.commit()
    db.refresh(entry)
    return entry


def run_auto_approve(
    db: Session,
    *,
    organization_id: uuid.UUID,
    as_of: date | None = None,
    business_days: int = 3,
) -> list[TimeEntry]:
    """Q12: auto-approve submissions after N business days without supervisor action."""
    as_of = as_of or date.today()
    org = db.get(Organization, organization_id)
    if org and isinstance(org.settings, dict):
        business_days = int(org.settings.get("auto_approve_business_days", business_days))

    pending = list(
        db.scalars(
            select(TimeEntry)
            .options(joinedload(TimeEntry.shift))
            .where(
                TimeEntry.organization_id == organization_id,
                TimeEntry.status == TimeEntryStatus.SUBMETIDO,
                TimeEntry.submitted_at.is_not(None),
            )
        ).unique()
    )
    approved: list[TimeEntry] = []
    for entry in pending:
        submitted_day = entry.submitted_at.date()  # type: ignore[union-attr]
        due = add_business_days(submitted_day, business_days)
        if as_of >= due:
            validate_entry(
                db,
                organization_id=organization_id,
                entry=entry,
                action="APROVAR",
                auto=True,
                adjustment_note=f"Auto após {business_days} dias úteis (Q12)",
            )
            approved.append(entry)
    return approved
