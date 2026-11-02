"""Billing models (Q10) + pre-billing drafts with Q11 cap + monthly periods (Q15)."""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    BillingModel,
    ContractType,
    DraftStatus,
    PeriodStatus,
    ServiceArea,
    TimeEntryStatus,
)
from app.models import (
    BillingDraft,
    BillingDraftLine,
    BillingPeriod,
    Client,
    Contract,
    ContractLine,
    CostEntry,
    Shift,
    TimeEntry,
)
from app.services.validation import money

ARTICLE_BY_AREA = {
    ServiceArea.REPOSICAO: "ART_REP",
    ServiceArea.PROMOCAO: "ART_PROM",
    ServiceArea.LOGISTICA: "ART_LOG",
    ServiceArea.EQUIPAS_FIXAS: "ART_EQ",
}

COST_CENTER_BY_AREA = {
    ServiceArea.REPOSICAO: "CC-REP",
    ServiceArea.PROMOCAO: "CC-PROM",
    ServiceArea.LOGISTICA: "CC-LOG",
    ServiceArea.EQUIPAS_FIXAS: "CC-EQ",
}

DEFAULT_VAT = Decimal("23.00")


def billing_model_for(contract_type: str) -> str:
    """Q10 defaults: hours for reposicao/promocao; fixed for logistica/equipas."""
    if contract_type in {ContractType.REPOSICAO, ContractType.PROMOCAO}:
        return BillingModel.HORAS_CONTRATADAS
    return BillingModel.VALOR_FIXO


def line_generates_daily_shifts(contract_type: str) -> bool:
    """Q06: Equipas Fixas — monthly billing + absences; no daily shifts in MVP."""
    return contract_type != ContractType.EQUIPAS_FIXAS


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def ensure_billing_period(
    db: Session,
    *,
    organization_id: uuid.UUID,
    year: int,
    month: int,
    service_area: str,
) -> BillingPeriod:
    existing = db.scalar(
        select(BillingPeriod).where(
            BillingPeriod.organization_id == organization_id,
            BillingPeriod.year == year,
            BillingPeriod.month == month,
            BillingPeriod.service_area == service_area,
        )
    )
    if existing:
        return existing
    start, end = month_bounds(year, month)
    period = BillingPeriod(
        organization_id=organization_id,
        year=year,
        month=month,
        service_area=service_area,
        start_date=start,
        end_date=end,
        status=PeriodStatus.ABERTO,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def ensure_month_periods(
    db: Session,
    *,
    organization_id: uuid.UUID,
    year: int,
    month: int,
) -> list[BillingPeriod]:
    return [
        ensure_billing_period(
            db, organization_id=organization_id, year=year, month=month, service_area=area
        )
        for area in ServiceArea
    ]


class BillingError(Exception):
    pass


def generate_prebilling(
    db: Session,
    *,
    organization_id: uuid.UUID,
    period: BillingPeriod,
    vat_rate: Decimal = DEFAULT_VAT,
) -> list[BillingDraft]:
    """Build drafts per client/contract for the period area using Q10/Q11 rules."""
    if period.status == PeriodStatus.FECHADO:
        raise BillingError("Período fechado")

    # Clear previous drafts for re-generation while open
    existing = list(db.scalars(select(BillingDraft).where(BillingDraft.period_id == period.id)))
    for d in existing:
        db.delete(d)
    db.flush()

    contracts = list(
        db.scalars(
            select(Contract)
            .options(joinedload(Contract.lines), joinedload(Contract.client))
            .where(
                Contract.organization_id == organization_id,
                Contract.type == period.service_area,
                Contract.status == "ATIVO",
            )
        ).unique()
    )

    drafts: list[BillingDraft] = []
    for contract in contracts:
        lines_out: list[BillingDraftLine] = []
        total_net = Decimal("0.00")

        for cline in contract.lines:
            if cline.service_type != period.service_area and cline.service_type != contract.type:
                continue
            model = contract.billing_model or billing_model_for(contract.type)
            article = ARTICLE_BY_AREA.get(period.service_area, "SERV_FIELD")
            cc = COST_CENTER_BY_AREA.get(period.service_area, "CC-GEN")

            if model == BillingModel.VALOR_FIXO:
                qty = Decimal("1.00")
                unit = money(cline.fixed_amount or 0)
                net = unit
                desc = f"{contract.number} · valor fixo · loja {str(cline.store_id)[:8]}"
                capped = False
                extra = False
            else:
                # Hours-based: use approved billable when available, else contracted (Q10)
                entries = _approved_entries_for_line(db, organization_id, cline.id, period)
                if entries:
                    qty = money(sum((e.hours_billable for e in entries), Decimal("0")))
                    extra = any(e.allow_extra_billable for e in entries)
                    # Q11: if any entry allowed extra, quantity may exceed contracted
                    contracted_cap = money(cline.contracted_hours or 0)
                    if contracted_cap > 0 and not extra:
                        qty = min(qty, contracted_cap)
                        capped = True
                    else:
                        capped = contracted_cap > 0 and qty <= contracted_cap
                else:
                    qty = money(cline.contracted_hours or 0)
                    capped = True
                    extra = False
                unit = money(cline.bill_rate or 0)
                net = money(qty * unit)
                desc = f"{contract.number} · horas · loja {str(cline.store_id)[:8]}"

            lines_out.append(
                {
                    "contract_line_id": cline.id,
                    "article_code": article,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit,
                    "line_net": net,
                    "billing_model": model,
                    "capped": capped if model == BillingModel.HORAS_CONTRATADAS else False,
                    "extra_override": extra if model == BillingModel.HORAS_CONTRATADAS else False,
                    "cost_center": cc,
                }
            )
            total_net += net

        if not lines_out:
            continue

        vat = money(total_net * (vat_rate / Decimal("100")))
        draft = BillingDraft(
            organization_id=organization_id,
            period_id=period.id,
            client_id=contract.client_id,
            contract_id=contract.id,
            status=DraftStatus.RASCUNHO,
            currency="EUR",
            total_net=money(total_net),
            total_vat=vat,
            total_gross=money(total_net + vat),
            vat_rate=vat_rate,
            cost_center=COST_CENTER_BY_AREA.get(period.service_area),
        )
        db.add(draft)
        db.flush()
        for raw in lines_out:
            db.add(
                BillingDraftLine(
                    organization_id=organization_id,
                    draft_id=draft.id,
                    **raw,
                )
            )
        drafts.append(draft)

    db.commit()
    return [
        db.scalar(
            select(BillingDraft)
            .options(joinedload(BillingDraft.lines), joinedload(BillingDraft.client))
            .where(BillingDraft.id == d.id)
        )
        for d in drafts
    ]


def _approved_entries_for_line(
    db: Session,
    organization_id: uuid.UUID,
    contract_line_id: uuid.UUID,
    period: BillingPeriod,
) -> list[TimeEntry]:
    return list(
        db.scalars(
            select(TimeEntry)
            .join(Shift, Shift.id == TimeEntry.shift_id)
            .where(
                TimeEntry.organization_id == organization_id,
                Shift.contract_line_id == contract_line_id,
                TimeEntry.status == TimeEntryStatus.APROVADO,
                Shift.planned_start >= datetime_start(period.start_date),
                Shift.planned_start < datetime_end_exclusive(period.end_date),
            )
        )
    )


def datetime_start(d: date):
    from datetime import datetime, timezone

    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def datetime_end_exclusive(d: date):
    from datetime import datetime, timedelta, timezone

    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1)


def apply_extra_override(
    db: Session,
    *,
    organization_id: uuid.UUID,
    line: BillingDraftLine,
    quantity: Decimal,
    reason: str,
) -> BillingDraftLine:
    """Q11 manual extra beyond contracted cap."""
    line.quantity = money(quantity)
    line.line_net = money(line.quantity * line.unit_price)
    line.extra_override = True
    line.capped = False
    line.extra_reason = reason
    draft = db.get(BillingDraft, line.draft_id)
    if draft and draft.organization_id == organization_id:
        total = money(sum((ln.line_net for ln in draft.lines), Decimal("0")))
        draft.total_net = total
        draft.total_vat = money(total * (draft.vat_rate / Decimal("100")))
        draft.total_gross = money(draft.total_net + draft.total_vat)
    db.commit()
    db.refresh(line)
    return line


def contract_margin(
    db: Session,
    *,
    organization_id: uuid.UUID,
    contract_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    contract = db.scalar(
        select(Contract)
        .options(joinedload(Contract.lines), joinedload(Contract.client))
        .where(Contract.id == contract_id, Contract.organization_id == organization_id)
    )
    if not contract:
        raise BillingError("Contrato não encontrado")

    # Expected revenue: hours * rate or fixed amount on lines
    expected_revenue = Decimal("0.00")
    for line in contract.lines:
        if contract.billing_model == BillingModel.VALOR_FIXO:
            expected_revenue += money(line.fixed_amount or 0)
        else:
            expected_revenue += money((line.contracted_hours or 0) * (line.bill_rate or 0))

    q = select(CostEntry).where(
        CostEntry.organization_id == organization_id,
        CostEntry.contract_id == contract_id,
    )
    if year is not None:
        q = q.where(CostEntry.period_year == year)
    if month is not None:
        q = q.where(CostEntry.period_month == month)
    costs = list(db.scalars(q))
    total_cost = money(sum((c.amount for c in costs), Decimal("0")))
    margin = money(expected_revenue - total_cost)
    pct = money((margin / expected_revenue) * 100) if expected_revenue else Decimal("0.00")
    return {
        "contract_id": str(contract.id),
        "contract_number": contract.number,
        "client_name": contract.client.name if contract.client else None,
        "expected_revenue": str(expected_revenue),
        "direct_costs": str(total_cost),
        "expected_margin": str(margin),
        "margin_pct": str(pct),
        "currency": "EUR",
        "cost_entries": len(costs),
    }
