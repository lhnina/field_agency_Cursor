"""PR4 ops: zones, budgets, CSV import, notifications, audit, period locks."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.db import get_db
from app.domain.enums import BudgetStatus
from app.models import (
    AuditLog,
    BillingPeriod,
    Budget,
    Campaign,
    Client,
    EmailOutbox,
    Notification,
    PayrollPeriod,
    User,
    Zone,
)
from app.schemas.common import (
    AuditLogOut,
    BudgetCreate,
    BudgetOut,
    CampaignOut,
    EmailOutboxOut,
    NotificationOut,
    PeriodReopenIn,
    ZoneCreate,
    ZoneOut,
)
from app.services.budgets import BudgetError, approve_budget_to_contract_campaign
from app.services.periods import (
    PeriodError,
    close_billing_period,
    close_payroll_period,
    reopen_billing_period,
    reopen_payroll_period,
)
from app.services.stores_import import ImportError_, ensure_zone, import_stores_csv

router = APIRouter(tags=["ops"])


class StoresImportResult(BaseModel):
    created: int
    skipped: int


@router.get("/zones", response_model=list[ZoneOut])
def list_zones(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Zone]:
    return list(
        db.scalars(
            select(Zone)
            .where(Zone.organization_id == user.organization_id)
            .order_by(Zone.code)
        )
    )


@router.post("/zones", response_model=ZoneOut, status_code=201)
def create_zone(
    payload: ZoneCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Zone:
    zone = ensure_zone(
        db,
        organization_id=user.organization_id,
        code=payload.code.strip(),
        name=payload.name.strip() if payload.name else payload.code.strip(),
    )
    if payload.name and zone.name != payload.name:
        zone.name = payload.name
    zone.active = payload.active
    db.commit()
    db.refresh(zone)
    return zone


@router.post("/stores/import-csv", response_model=StoresImportResult)
async def import_stores(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoresImportResult:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV deve ser UTF-8") from exc
    try:
        result = import_stores_csv(
            db,
            organization_id=user.organization_id,
            content=text,
            actor_user_id=user.id,
        )
    except ImportError_ as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StoresImportResult(**result)


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[BudgetOut]:
    rows = list(
        db.scalars(
            select(Budget)
            .options(joinedload(Budget.client))
            .where(Budget.organization_id == user.organization_id)
            .order_by(Budget.created_at.desc())
        ).unique()
    )
    return [_budget_out(b) for b in rows]


@router.post("/budgets", response_model=BudgetOut, status_code=201)
def create_budget(
    payload: BudgetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetOut:
    client = db.scalar(
        select(Client).where(Client.id == payload.client_id, Client.organization_id == user.organization_id)
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    budget = Budget(
        organization_id=user.organization_id,
        client_id=payload.client_id,
        brand_id=payload.brand_id,
        number=payload.number,
        title=payload.title,
        contract_type=payload.contract_type,
        status=BudgetStatus.RASCUNHO,
        valid_until=payload.valid_until,
        lines=payload.lines,
        total_amount=payload.total_amount,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    budget = db.scalar(
        select(Budget).options(joinedload(Budget.client)).where(Budget.id == budget.id)
    )
    assert budget is not None
    return _budget_out(budget)


@router.post("/budgets/{budget_id}/approve-convert", response_model=BudgetOut)
def convert_budget(
    budget_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetOut:
    budget = db.scalar(
        select(Budget)
        .options(joinedload(Budget.client))
        .where(Budget.id == budget_id, Budget.organization_id == user.organization_id)
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if budget.status == BudgetStatus.RASCUNHO:
        budget.status = BudgetStatus.APROVADO
        db.flush()
    try:
        budget, _contract, _campaign = approve_budget_to_contract_campaign(
            db,
            organization_id=user.organization_id,
            budget=budget,
            actor_user_id=user.id,
        )
    except BudgetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    budget = db.scalar(
        select(Budget).options(joinedload(Budget.client)).where(Budget.id == budget.id)
    )
    assert budget is not None
    return _budget_out(budget)


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Campaign]:
    return list(
        db.scalars(
            select(Campaign)
            .where(Campaign.organization_id == user.organization_id)
            .order_by(Campaign.created_at.desc())
        )
    )


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    q = select(Notification).where(
        Notification.organization_id == user.organization_id,
        (Notification.user_id == user.id) | (Notification.user_id.is_(None)),
    )
    if unread_only:
        q = q.where(Notification.read.is_(False))
    return list(db.scalars(q.order_by(Notification.created_at.desc()).limit(100)))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    n = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == user.organization_id,
        )
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


@router.get("/email-outbox", response_model=list[EmailOutboxOut])
def list_email_outbox(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmailOutbox]:
    return list(
        db.scalars(
            select(EmailOutbox)
            .where(EmailOutbox.organization_id == user.organization_id)
            .order_by(EmailOutbox.created_at.desc())
            .limit(50)
        )
    )


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    q = select(AuditLog).where(AuditLog.organization_id == user.organization_id)
    if action:
        q = q.where(AuditLog.action == action)
    return list(db.scalars(q.order_by(AuditLog.created_at.desc()).limit(limit)))


@router.post("/billing-periods/{period_id}/close", response_model=dict)
def close_billing(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    period = _billing_period(db, user.organization_id, period_id)
    try:
        period = close_billing_period(db, period=period, actor_user_id=user.id)
    except PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(period.id), "status": period.status, "closed_at": period.closed_at}


@router.post("/billing-periods/{period_id}/reopen", response_model=dict)
def reopen_billing(
    period_id: uuid.UUID,
    payload: PeriodReopenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    period = _billing_period(db, user.organization_id, period_id)
    try:
        period = reopen_billing_period(
            db, period=period, actor_user_id=user.id, reason=payload.reason
        )
    except PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(period.id), "status": period.status, "reopen_reason": period.reopen_reason}


@router.post("/payroll-periods/{period_id}/close", response_model=dict)
def close_payroll(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    period = _payroll_period(db, user.organization_id, period_id)
    try:
        period = close_payroll_period(db, period=period, actor_user_id=user.id)
    except PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(period.id), "status": period.status, "closed_at": period.closed_at}


@router.post("/payroll-periods/{period_id}/reopen", response_model=dict)
def reopen_payroll(
    period_id: uuid.UUID,
    payload: PeriodReopenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    period = _payroll_period(db, user.organization_id, period_id)
    try:
        period = reopen_payroll_period(
            db, period=period, actor_user_id=user.id, reason=payload.reason
        )
    except PeriodError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(period.id), "status": period.status, "reopen_reason": period.reopen_reason}


def _billing_period(db: Session, organization_id: uuid.UUID, period_id: uuid.UUID) -> BillingPeriod:
    period = db.scalar(
        select(BillingPeriod).where(
            BillingPeriod.id == period_id, BillingPeriod.organization_id == organization_id
        )
    )
    if not period:
        raise HTTPException(status_code=404, detail="Período de faturação não encontrado")
    return period


def _payroll_period(db: Session, organization_id: uuid.UUID, period_id: uuid.UUID) -> PayrollPeriod:
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id, PayrollPeriod.organization_id == organization_id
        )
    )
    if not period:
        raise HTTPException(status_code=404, detail="Período de apuramento não encontrado")
    return period


def _budget_out(b: Budget) -> BudgetOut:
    return BudgetOut(
        id=b.id,
        organization_id=b.organization_id,
        client_id=b.client_id,
        client_name=b.client.name if b.client else None,
        brand_id=b.brand_id,
        number=b.number,
        title=b.title,
        contract_type=b.contract_type,
        status=b.status,
        valid_until=b.valid_until,
        lines=b.lines if isinstance(b.lines, list) else [],
        total_amount=b.total_amount,
        resulting_contract_id=b.resulting_contract_id,
        resulting_campaign_id=b.resulting_campaign_id,
        created_at=b.created_at,
    )
