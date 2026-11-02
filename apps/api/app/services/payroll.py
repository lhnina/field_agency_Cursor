"""Payroll settlement map + remuneraçao CSV (Q13 / Q14 / Q15)."""

from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import PeriodStatus, TimeEntryStatus
from app.models import (
    Assignment,
    Contract,
    ContractLine,
    Employee,
    PayrollPeriod,
    PayrollStatement,
    Shift,
    TimeEntry,
)
from app.services.billing import month_bounds
from app.services.validation import money


def ensure_payroll_period(
    db: Session,
    *,
    organization_id: uuid.UUID,
    year: int,
    month: int,
) -> PayrollPeriod:
    existing = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.organization_id == organization_id,
            PayrollPeriod.year == year,
            PayrollPeriod.month == month,
        )
    )
    if existing:
        return existing
    start, end = month_bounds(year, month)
    period = PayrollPeriod(
        organization_id=organization_id,
        year=year,
        month=month,
        start_date=start,
        end_date=end,
        status=PeriodStatus.ABERTO,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def generate_payroll_statements(
    db: Session,
    *,
    organization_id: uuid.UUID,
    period: PayrollPeriod,
) -> list[PayrollStatement]:
    """Aggregate approved payable hours per employee × client → Cliente, Horas, Valor."""
    from app.services.billing import datetime_end_exclusive, datetime_start

    # wipe previous statements for regen
    for old in list(db.scalars(select(PayrollStatement).where(PayrollStatement.period_id == period.id))):
        db.delete(old)
    db.flush()

    entries = list(
        db.scalars(
            select(TimeEntry)
            .options(
                joinedload(TimeEntry.shift)
                .joinedload(Shift.assignments)
                .joinedload(Assignment.employee),
                joinedload(TimeEntry.shift).joinedload(Shift.store),
            )
            .join(Shift, Shift.id == TimeEntry.shift_id)
            .where(
                TimeEntry.organization_id == organization_id,
                TimeEntry.status == TimeEntryStatus.APROVADO,
                Shift.planned_start >= datetime_start(period.start_date),
                Shift.planned_start < datetime_end_exclusive(period.end_date),
            )
        ).unique()
    )

    # Load contract lines → clients
    line_ids = {e.shift.contract_line_id for e in entries if e.shift}
    lines = {
        ln.id: ln
        for ln in db.scalars(select(ContractLine).where(ContractLine.id.in_(line_ids))).all()
    } if line_ids else {}
    contract_ids = {ln.contract_id for ln in lines.values()}
    contracts = {
        c.id: c
        for c in db.scalars(
            select(Contract).options(joinedload(Contract.client)).where(Contract.id.in_(contract_ids))
        ).unique().all()
    } if contract_ids else {}

    agg: dict[tuple[uuid.UUID, str], dict] = {}
    for entry in entries:
        shift = entry.shift
        if not shift:
            continue
        asg = next((a for a in shift.assignments if a.active), None)
        if not asg or not asg.employee:
            continue
        emp = asg.employee
        cline = lines.get(shift.contract_line_id)
        contract = contracts.get(cline.contract_id) if cline else None
        client = contract.client if contract else None
        client_name = client.name if client else "Sem cliente"
        client_id = client.id if client else None
        key = (emp.id, client_name)
        bucket = agg.setdefault(
            key,
            {
                "employee": emp,
                "client_id": client_id,
                "client_name": client_name,
                "hours": Decimal("0"),
                "amount": Decimal("0"),
            },
        )
        hours = money(entry.hours_payable or 0)
        # Q14: RV uses preço/hora; CT uses hourly_cost as settlement stub
        if emp.engagement_type == "RV":
            rate = money(emp.rv_hourly_rate or emp.hourly_cost or 0)
        else:
            rate = money(emp.hourly_cost or 0)
        bucket["hours"] += hours
        bucket["amount"] += money(hours * rate)

    statements: list[PayrollStatement] = []
    for data in agg.values():
        emp: Employee = data["employee"]
        rate = money(emp.rv_hourly_rate or emp.hourly_cost or 0) if emp.engagement_type == "RV" else money(emp.hourly_cost or 0)
        st = PayrollStatement(
            organization_id=organization_id,
            period_id=period.id,
            employee_id=emp.id,
            client_id=data["client_id"],
            client_name=data["client_name"],
            hours=money(data["hours"]),
            amount=money(data["amount"]),
            engagement_type=emp.engagement_type,
            hourly_rate=rate,
            currency="EUR",
        )
        db.add(st)
        statements.append(st)
    db.commit()
    return statements


def payroll_csv(statements: list[PayrollStatement]) -> str:
    """Q13: Cliente, Horas, Valor."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Cliente", "Horas", "Valor", "Colaborador", "Vinculo", "Moeda"])
    for s in statements:
        writer.writerow(
            [
                s.client_name,
                f"{money(s.hours):.2f}",
                f"{money(s.amount):.2f}",
                s.employee.full_name if s.employee else "",
                s.engagement_type,
                s.currency,
            ]
        )
    return buf.getvalue()
