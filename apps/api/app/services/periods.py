"""Period close hard-lock + audited reopen."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import PeriodStatus
from app.models import BillingPeriod, PayrollPeriod
from app.services.audit import write_audit


class PeriodError(Exception):
    pass


def assert_billing_period_open(period: BillingPeriod) -> None:
    if period.status == PeriodStatus.FECHADO:
        raise PeriodError("Período de faturação fechado — reabrir com auditoria")


def assert_payroll_period_open(period: PayrollPeriod) -> None:
    if period.status == PeriodStatus.FECHADO:
        raise PeriodError("Período de apuramento fechado — reabrir com auditoria")


def close_billing_period(
    db: Session,
    *,
    period: BillingPeriod,
    actor_user_id: uuid.UUID,
) -> BillingPeriod:
    if period.status == PeriodStatus.FECHADO:
        raise PeriodError("Período já fechado")
    before = {"status": period.status}
    period.status = PeriodStatus.FECHADO
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by_user_id = actor_user_id
    period.reopen_reason = None
    write_audit(
        db,
        organization_id=period.organization_id,
        actor_user_id=actor_user_id,
        action="PERIOD_CLOSE",
        entity_type="billing_period",
        entity_id=period.id,
        before=before,
        after={"status": period.status},
    )
    db.commit()
    db.refresh(period)
    return period


def reopen_billing_period(
    db: Session,
    *,
    period: BillingPeriod,
    actor_user_id: uuid.UUID,
    reason: str,
) -> BillingPeriod:
    if period.status != PeriodStatus.FECHADO:
        raise PeriodError("Período não está fechado")
    if not reason.strip():
        raise PeriodError("Motivo de reabertura obrigatório")
    before = {"status": period.status}
    period.status = PeriodStatus.ABERTO
    period.reopen_reason = reason
    write_audit(
        db,
        organization_id=period.organization_id,
        actor_user_id=actor_user_id,
        action="PERIOD_REOPEN",
        entity_type="billing_period",
        entity_id=period.id,
        before=before,
        after={"status": period.status, "reason": reason},
    )
    db.commit()
    db.refresh(period)
    return period


def close_payroll_period(
    db: Session,
    *,
    period: PayrollPeriod,
    actor_user_id: uuid.UUID,
) -> PayrollPeriod:
    if period.status == PeriodStatus.FECHADO:
        raise PeriodError("Período já fechado")
    before = {"status": period.status}
    period.status = PeriodStatus.FECHADO
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by_user_id = actor_user_id
    write_audit(
        db,
        organization_id=period.organization_id,
        actor_user_id=actor_user_id,
        action="PERIOD_CLOSE",
        entity_type="payroll_period",
        entity_id=period.id,
        before=before,
        after={"status": period.status},
    )
    db.commit()
    db.refresh(period)
    return period


def reopen_payroll_period(
    db: Session,
    *,
    period: PayrollPeriod,
    actor_user_id: uuid.UUID,
    reason: str,
) -> PayrollPeriod:
    if period.status != PeriodStatus.FECHADO:
        raise PeriodError("Período não está fechado")
    if not reason.strip():
        raise PeriodError("Motivo de reabertura obrigatório")
    before = {"status": period.status}
    period.status = PeriodStatus.ABERTO
    period.reopen_reason = reason
    write_audit(
        db,
        organization_id=period.organization_id,
        actor_user_id=actor_user_id,
        action="PERIOD_REOPEN",
        entity_type="payroll_period",
        entity_id=period.id,
        before=before,
        after={"status": period.status, "reason": reason},
    )
    db.commit()
    db.refresh(period)
    return period
