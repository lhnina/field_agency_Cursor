"""Operational alerts: unassigned shifts, document expiry, CT soft alerts (Q20)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import AlertKind, DocumentStatus
from app.models import Assignment, EmployeeDocument, Shift
from app.services.assignments import find_overlapping_shifts, unassigned_shifts_in_range


def collect_alerts(
    db: Session,
    *,
    organization_id: uuid.UUID,
    week_start: date | None = None,
    doc_horizon_days: int = 30,
) -> list[dict[str, Any]]:
    today = date.today()
    if week_start is None:
        # Monday of current ISO week relative to "today" — demo often pins 2026-11-02
        week_start = today - timedelta(days=today.weekday())

    start_dt = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=7)
    alerts: list[dict[str, Any]] = []

    for shift in unassigned_shifts_in_range(
        db, organization_id=organization_id, start=start_dt, end=end_dt
    ):
        alerts.append(
            {
                "kind": AlertKind.UNASSIGNED_SHIFT,
                "severity": "warning",
                "title": "Serviço sem recurso",
                "message": f"{shift.store.name if shift.store else 'Loja'} · {shift.planned_start.isoformat()}",
                "entity_type": "shift",
                "entity_id": str(shift.id),
            }
        )

    horizon = today + timedelta(days=doc_horizon_days)
    docs = list(
        db.scalars(
            select(EmployeeDocument)
            .options(joinedload(EmployeeDocument.employee))
            .where(
                EmployeeDocument.organization_id == organization_id,
                EmployeeDocument.expires_on.is_not(None),
                EmployeeDocument.expires_on <= horizon,
            )
            .order_by(EmployeeDocument.expires_on)
        ).unique()
    )
    for doc in docs:
        expired = doc.expires_on is not None and doc.expires_on < today
        if expired and doc.status != DocumentStatus.EXPIRADO:
            doc.status = DocumentStatus.EXPIRADO
        alerts.append(
            {
                "kind": AlertKind.DOC_EXPIRED if expired else AlertKind.DOC_EXPIRING,
                "severity": "danger" if expired else "warning",
                "title": "Documento expirado" if expired else "Documento a expirar",
                "message": (
                    f"{doc.employee.full_name} · {doc.doc_type}"
                    f"{' — ' + doc.label if doc.label else ''} · {doc.expires_on.isoformat()}"
                ),
                "entity_type": "employee_document",
                "entity_id": str(doc.id),
            }
        )
    db.commit()

    # Soft overlap scan for the week (should be rare if assign enforces hard block)
    week_shifts = list(
        db.scalars(
            select(Shift)
            .options(joinedload(Shift.assignments))
            .where(
                Shift.organization_id == organization_id,
                Shift.planned_start >= start_dt,
                Shift.planned_start < end_dt,
            )
        ).unique()
    )
    seen_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for shift in week_shifts:
        for asg in shift.assignments:
            if not asg.active:
                continue
            overlaps = find_overlapping_shifts(
                db,
                organization_id=organization_id,
                employee_id=asg.employee_id,
                planned_start=shift.planned_start,
                planned_end=shift.planned_end,
                exclude_shift_id=shift.id,
            )
            for other in overlaps:
                key = tuple(sorted((shift.id, other.id)))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                alerts.append(
                    {
                        "kind": AlertKind.OVERLAP,
                        "severity": "danger",
                        "title": "Sobreposição de turnos",
                        "message": f"Colaborador {asg.employee_id} com turnos sobrepostos",
                        "entity_type": "shift",
                        "entity_id": str(shift.id),
                    }
                )

    # CT alerts only (Q20) — placeholder soft signal when a CT collaborator has >5 shifts in week
    from app.models import Employee

    employees = {
        e.id: e
        for e in db.scalars(
            select(Employee).where(Employee.organization_id == organization_id)
        )
    }
    counts: dict[uuid.UUID, int] = {}
    for shift in week_shifts:
        for asg in shift.assignments:
            if asg.active:
                counts[asg.employee_id] = counts.get(asg.employee_id, 0) + 1
    for emp_id, count in counts.items():
        emp = employees.get(emp_id)
        if emp and emp.engagement_type == "CT" and count >= 6:
            alerts.append(
                {
                    "kind": AlertKind.CT_HOURS,
                    "severity": "info",
                    "title": "Alerta CT (informativo)",
                    "message": (
                        f"{emp.full_name}: {count} turnos na semana — "
                        "só alerta no MVP (Q20), sem bloqueio"
                    ),
                    "entity_type": "employee",
                    "entity_id": str(emp_id),
                }
            )

    return alerts
