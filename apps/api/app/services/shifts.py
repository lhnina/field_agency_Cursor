from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import HourConcept, ShiftStatus
from app.models import Assignment, ContractLine, ServicePlan, Shift, TimeEntry, TimeStateHistory


WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def generate_shifts_for_week(
    db: Session,
    *,
    organization_id: uuid.UUID,
    service_plan: ServicePlan,
    week_start: date,
    author_user_id: uuid.UUID | None = None,
) -> list[Shift]:
    """Stub recurrence generator: weekly weekdays + start/end times from schedule_rules."""
    line = db.get(ContractLine, service_plan.contract_line_id)
    if not line or not line.generates_daily_shifts:
        return []

    rule = service_plan.recurrence_rule or {}
    days = rule.get("weekdays") or line.schedule_rules.get("weekdays") or ["mon", "wed", "fri"]
    start_s = rule.get("start_time") or line.schedule_rules.get("start_time") or "09:00"
    end_s = rule.get("end_time") or line.schedule_rules.get("end_time") or "12:00"
    start_t = _parse_hhmm(start_s)
    end_t = _parse_hhmm(end_s)

    created: list[Shift] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        weekday_key = next((k for k, v in WEEKDAY_MAP.items() if v == day.weekday()), None)
        if weekday_key not in days:
            continue

        # Skip if shift already exists for this plan/day
        existing = db.scalar(
            select(Shift).where(
                Shift.service_plan_id == service_plan.id,
                Shift.planned_start >= datetime.combine(day, time.min, tzinfo=timezone.utc),
                Shift.planned_start < datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc),
            )
        )
        if existing:
            continue

        planned_start = datetime.combine(day, start_t, tzinfo=timezone.utc)
        planned_end = datetime.combine(day, end_t, tzinfo=timezone.utc)
        hours = Decimal(str((planned_end - planned_start).total_seconds() / 3600))

        shift = Shift(
            organization_id=organization_id,
            contract_line_id=line.id,
            service_plan_id=service_plan.id,
            store_id=line.store_id,
            planned_start=planned_start,
            planned_end=planned_end,
            status=ShiftStatus.PLANEADO,
            shift_type=line.service_type,
        )
        db.add(shift)
        db.flush()

        assigned_hours = Decimal("0")
        if service_plan.default_employee_id:
            db.add(
                Assignment(
                    organization_id=organization_id,
                    shift_id=shift.id,
                    employee_id=service_plan.default_employee_id,
                    role="EXECUTOR",
                    is_substitute=False,
                    active=True,
                )
            )
            shift.status = ShiftStatus.ATRIBUIDO
            assigned_hours = hours

        entry = TimeEntry(
            organization_id=organization_id,
            shift_id=shift.id,
            hours_contracted=line.contracted_hours or hours,
            hours_planned=hours,
            hours_assigned=assigned_hours,
            hours_executed=Decimal("0"),
            hours_approved=Decimal("0"),
            hours_billable=Decimal("0"),
            hours_payable=Decimal("0"),
            status="RASCUNHO",
        )
        db.add(entry)
        db.flush()

        for concept, value in (
            (HourConcept.CONTRATADAS, entry.hours_contracted),
            (HourConcept.PLANEADAS, entry.hours_planned),
            (HourConcept.AFETADAS, entry.hours_assigned),
        ):
            db.add(
                TimeStateHistory(
                    organization_id=organization_id,
                    time_entry_id=entry.id,
                    concept=concept,
                    hours=value,
                    reason="Geração de turnos (stub)",
                    author_user_id=author_user_id,
                )
            )

        created.append(shift)

    db.commit()
    for shift in created:
        db.refresh(shift)
    return created


def planning_week(
    db: Session,
    *,
    organization_id: uuid.UUID,
    week_start: date,
) -> list[Shift]:
    week_end = week_start + timedelta(days=7)
    start_dt = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end, time.min, tzinfo=timezone.utc)
    return list(
        db.scalars(
            select(Shift)
            .options(
                joinedload(Shift.assignments).joinedload(Assignment.employee),
                joinedload(Shift.store),
            )
            .where(
                Shift.organization_id == organization_id,
                Shift.planned_start >= start_dt,
                Shift.planned_start < end_dt,
            )
            .order_by(Shift.planned_start)
        ).unique()
    )
