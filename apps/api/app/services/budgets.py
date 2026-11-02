"""Orçamento aprovado → Contrato + Campanha (Q02)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import BudgetStatus, ContractType
from app.models import Brand, Budget, Campaign, Client, Contract, ContractLine, Store
from app.services.audit import write_audit
from app.services.billing import billing_model_for, line_generates_daily_shifts
from app.services.validation import money


class BudgetError(Exception):
    pass


def approve_budget_to_contract_campaign(
    db: Session,
    *,
    organization_id: uuid.UUID,
    budget: Budget,
    actor_user_id: uuid.UUID | None = None,
) -> tuple[Budget, Contract, Campaign]:
    if budget.status == BudgetStatus.CONVERTIDO:
        raise BudgetError("Orçamento já convertido")
    if budget.status not in {BudgetStatus.APROVADO, BudgetStatus.ENVIADO, BudgetStatus.RASCUNHO}:
        raise BudgetError("Estado de orçamento inválido para conversão")

    client = db.get(Client, budget.client_id)
    if not client or client.organization_id != organization_id:
        raise BudgetError("Cliente inválido")

    contract = Contract(
        organization_id=organization_id,
        client_id=budget.client_id,
        brand_id=budget.brand_id,
        number=f"CT-FROM-{budget.number}",
        type=budget.contract_type,
        billing_model=billing_model_for(budget.contract_type),
        start_date=date.today(),
        status="ATIVO",
        version=1,
        notes=f"Gerado a partir do orçamento {budget.number} (Q02)",
    )
    db.add(contract)
    db.flush()

    # Optional store lines from budget.lines[{store_id, hours|fixed_amount, ...}]
    raw_lines = budget.lines if isinstance(budget.lines, list) else []
    for raw in raw_lines:
        store_id = raw.get("store_id")
        if not store_id:
            continue
        store = db.scalar(
            select(Store).where(Store.id == uuid.UUID(str(store_id)), Store.organization_id == organization_id)
        )
        if not store:
            continue
        db.add(
            ContractLine(
                organization_id=organization_id,
                contract_id=contract.id,
                store_id=store.id,
                service_type=budget.contract_type,
                contracted_hours=Decimal(str(raw["hours"])) if raw.get("hours") is not None else None,
                bill_rate=Decimal(str(raw["bill_rate"])) if raw.get("bill_rate") is not None else None,
                fixed_amount=Decimal(str(raw["fixed_amount"])) if raw.get("fixed_amount") is not None else None,
                schedule_rules=raw.get("schedule_rules") or {},
                pricing_components=raw.get("pricing_components") or {},
                start_date=contract.start_date,
                generates_daily_shifts=line_generates_daily_shifts(budget.contract_type),
            )
        )

    campaign = Campaign(
        organization_id=organization_id,
        client_id=budget.client_id,
        brand_id=budget.brand_id,
        contract_id=contract.id,
        budget_id=budget.id,
        name=f"Campanha · {budget.title}",
        start_date=date.today(),
        status="ATIVA",
    )
    db.add(campaign)
    db.flush()

    before = {"status": budget.status}
    budget.status = BudgetStatus.CONVERTIDO
    budget.resulting_contract_id = contract.id
    budget.resulting_campaign_id = campaign.id

    write_audit(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="BUDGET_CONVERT",
        entity_type="budget",
        entity_id=budget.id,
        before=before,
        after={
            "status": budget.status,
            "contract_id": str(contract.id),
            "campaign_id": str(campaign.id),
        },
    )
    db.commit()
    db.refresh(budget)
    db.refresh(contract)
    db.refresh(campaign)
    return budget, contract, campaign
