"""Validation, billing, payroll, PHC export, margin — PR3."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.db import get_db
from app.domain.enums import TimeEntryStatus
from app.models import (
    BillingDraft,
    BillingDraftLine,
    BillingPeriod,
    Contract,
    CostEntry,
    Employee,
    ErpExportBatch,
    PayrollPeriod,
    PayrollStatement,
    Shift,
    TimeEntry,
    User,
)
from app.schemas.common import (
    BillingDraftOut,
    BillingDraftLineOut,
    BillingPeriodCreate,
    BillingPeriodOut,
    CostEntryCreate,
    CostEntryOut,
    DashboardKpisOut,
    ErpExportBatchOut,
    ExtraOverrideIn,
    MarginOut,
    PayrollPeriodOut,
    PayrollStatementOut,
    SubmitHoursIn,
    TimeEntryOut,
    ValidateHoursIn,
)
from app.services.alerts import collect_alerts
from app.services.billing import (
    BillingError,
    apply_extra_override,
    contract_margin,
    ensure_billing_period,
    ensure_month_periods,
    generate_prebilling,
)
from app.services.payroll import ensure_payroll_period, generate_payroll_statements
from app.services.phc_export import (
    create_billing_export_batch,
    create_payroll_export_batch,
    mark_batch_sent,
)
from app.services.validation import ValidationError, run_auto_approve, submit_execution, validate_entry

router = APIRouter(tags=["finance"])


def _entry_out(entry: TimeEntry) -> TimeEntryOut:
    shift = entry.shift
    return TimeEntryOut(
        id=entry.id,
        shift_id=entry.shift_id,
        hours_contracted=entry.hours_contracted,
        hours_planned=entry.hours_planned,
        hours_assigned=entry.hours_assigned,
        hours_executed=entry.hours_executed,
        hours_approved=entry.hours_approved,
        hours_billable=entry.hours_billable,
        hours_payable=entry.hours_payable,
        status=entry.status,
        submitted_at=entry.submitted_at,
        approved_at=entry.approved_at,
        auto_approved=entry.auto_approved,
        allow_extra_billable=entry.allow_extra_billable,
        adjustment_note=entry.adjustment_note,
        tacit_accepted=entry.tacit_accepted,
        store_name=shift.store.name if shift and shift.store else None,
        shift_type=shift.shift_type if shift else None,
        planned_start=shift.planned_start if shift else None,
    )


def _draft_out(d: BillingDraft) -> BillingDraftOut:
    return BillingDraftOut(
        id=d.id,
        period_id=d.period_id,
        client_id=d.client_id,
        client_name=d.client.name if d.client else None,
        contract_id=d.contract_id,
        status=d.status,
        currency=d.currency,
        total_net=d.total_net,
        total_vat=d.total_vat,
        total_gross=d.total_gross,
        vat_rate=d.vat_rate,
        cost_center=d.cost_center,
        lines=[BillingDraftLineOut.model_validate(ln) for ln in d.lines],
    )


@router.get("/time-entries", response_model=list[TimeEntryOut])
def list_time_entries(
    status: str | None = None,
    week_start: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TimeEntryOut]:
    q = (
        select(TimeEntry)
        .options(joinedload(TimeEntry.shift).joinedload(Shift.store))
        .where(TimeEntry.organization_id == user.organization_id)
    )
    if status:
        q = q.where(TimeEntry.status == status)
    if week_start:
        from datetime import datetime, timedelta, timezone

        start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
        end = start + timedelta(days=7)
        q = q.join(Shift).where(Shift.planned_start >= start, Shift.planned_start < end)
    rows = list(db.scalars(q.order_by(TimeEntry.status)).unique())
    return [_entry_out(e) for e in rows]


@router.post("/time-entries/{entry_id}/submit", response_model=TimeEntryOut)
def submit_hours(
    entry_id: uuid.UUID,
    payload: SubmitHoursIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    entry = _get_entry(db, user.organization_id, entry_id)
    try:
        entry = submit_execution(
            db,
            organization_id=user.organization_id,
            entry=entry,
            hours_executed=payload.hours_executed,
            author_user_id=user.id,
            apply_tacit=payload.apply_tacit,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entry = _get_entry(db, user.organization_id, entry_id)
    return _entry_out(entry)


@router.post("/time-entries/{entry_id}/validate", response_model=TimeEntryOut)
def validate_hours(
    entry_id: uuid.UUID,
    payload: ValidateHoursIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    entry = _get_entry(db, user.organization_id, entry_id)
    try:
        entry = validate_entry(
            db,
            organization_id=user.organization_id,
            entry=entry,
            action=payload.action,
            hours_approved=payload.hours_approved,
            allow_extra_billable=payload.allow_extra_billable,
            adjustment_note=payload.adjustment_note,
            author_user_id=user.id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entry = _get_entry(db, user.organization_id, entry_id)
    return _entry_out(entry)


@router.post("/time-entries/auto-approve", response_model=list[TimeEntryOut])
def auto_approve(
    as_of: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TimeEntryOut]:
    approved = run_auto_approve(db, organization_id=user.organization_id, as_of=as_of)
    return [_entry_out(_get_entry(db, user.organization_id, e.id)) for e in approved]


@router.post("/billing-periods", response_model=list[BillingPeriodOut])
def create_periods(
    payload: BillingPeriodCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BillingPeriod]:
    if payload.service_area:
        return [
            ensure_billing_period(
                db,
                organization_id=user.organization_id,
                year=payload.year,
                month=payload.month,
                service_area=payload.service_area,
            )
        ]
    return ensure_month_periods(
        db, organization_id=user.organization_id, year=payload.year, month=payload.month
    )


@router.get("/billing-periods", response_model=list[BillingPeriodOut])
def list_periods(
    year: int | None = None,
    month: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BillingPeriod]:
    q = select(BillingPeriod).where(BillingPeriod.organization_id == user.organization_id)
    if year:
        q = q.where(BillingPeriod.year == year)
    if month:
        q = q.where(BillingPeriod.month == month)
    return list(db.scalars(q.order_by(BillingPeriod.service_area)))


@router.post("/billing-periods/{period_id}/generate", response_model=list[BillingDraftOut])
def generate_drafts(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BillingDraftOut]:
    period = db.scalar(
        select(BillingPeriod).where(
            BillingPeriod.id == period_id, BillingPeriod.organization_id == user.organization_id
        )
    )
    if not period:
        raise HTTPException(status_code=404, detail="Período não encontrado")
    try:
        drafts = generate_prebilling(db, organization_id=user.organization_id, period=period)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_draft_out(d) for d in drafts if d]


@router.get("/billing-drafts", response_model=list[BillingDraftOut])
def list_drafts(
    period_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BillingDraftOut]:
    q = (
        select(BillingDraft)
        .options(joinedload(BillingDraft.lines), joinedload(BillingDraft.client))
        .where(BillingDraft.organization_id == user.organization_id)
    )
    if period_id:
        q = q.where(BillingDraft.period_id == period_id)
    return [_draft_out(d) for d in db.scalars(q).unique()]


@router.post("/billing-draft-lines/{line_id}/extra", response_model=BillingDraftLineOut)
def extra_line(
    line_id: uuid.UUID,
    payload: ExtraOverrideIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingDraftLine:
    line = db.scalar(
        select(BillingDraftLine).where(
            BillingDraftLine.id == line_id,
            BillingDraftLine.organization_id == user.organization_id,
        )
    )
    if not line:
        raise HTTPException(status_code=404, detail="Linha não encontrada")
    line = apply_extra_override(
        db,
        organization_id=user.organization_id,
        line=line,
        quantity=payload.quantity,
        reason=payload.reason,
    )
    return BillingDraftLineOut.model_validate(line)


@router.post("/cost-entries", response_model=CostEntryOut, status_code=201)
def create_cost(
    payload: CostEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CostEntry:
    contract = db.scalar(
        select(Contract).where(
            Contract.id == payload.contract_id, Contract.organization_id == user.organization_id
        )
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    entry = CostEntry(organization_id=user.organization_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/cost-entries", response_model=list[CostEntryOut])
def list_costs(
    contract_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CostEntry]:
    q = select(CostEntry).where(CostEntry.organization_id == user.organization_id)
    if contract_id:
        q = q.where(CostEntry.contract_id == contract_id)
    return list(db.scalars(q.order_by(CostEntry.created_at.desc())))


@router.get("/contracts/{contract_id}/margin", response_model=MarginOut)
def get_margin(
    contract_id: uuid.UUID,
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarginOut:
    try:
        data = contract_margin(
            db,
            organization_id=user.organization_id,
            contract_id=contract_id,
            year=year,
            month=month,
        )
    except BillingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarginOut(**data)


@router.post("/payroll-periods", response_model=PayrollPeriodOut)
def create_payroll_period(
    year: int = Query(...),
    month: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PayrollPeriod:
    return ensure_payroll_period(db, organization_id=user.organization_id, year=year, month=month)


@router.post("/payroll-periods/{period_id}/generate", response_model=list[PayrollStatementOut])
def generate_payroll(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PayrollStatementOut]:
    period = db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id, PayrollPeriod.organization_id == user.organization_id
        )
    )
    if not period:
        raise HTTPException(status_code=404, detail="Período não encontrado")
    stmts = generate_payroll_statements(db, organization_id=user.organization_id, period=period)
    return [
        PayrollStatementOut(
            id=s.id,
            employee_id=s.employee_id,
            employee_name=s.employee.full_name if s.employee else None,
            client_name=s.client_name,
            hours=s.hours,
            amount=s.amount,
            engagement_type=s.engagement_type,
            hourly_rate=s.hourly_rate,
            currency=s.currency,
        )
        for s in db.scalars(
            select(PayrollStatement)
            .options(joinedload(PayrollStatement.employee))
            .where(PayrollStatement.period_id == period.id)
        ).unique()
    ]


@router.get("/payroll-periods/{period_id}/statements", response_model=list[PayrollStatementOut])
def list_statements(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PayrollStatementOut]:
    rows = list(
        db.scalars(
            select(PayrollStatement)
            .options(joinedload(PayrollStatement.employee))
            .where(
                PayrollStatement.period_id == period_id,
                PayrollStatement.organization_id == user.organization_id,
            )
        ).unique()
    )
    return [
        PayrollStatementOut(
            id=s.id,
            employee_id=s.employee_id,
            employee_name=s.employee.full_name if s.employee else None,
            client_name=s.client_name,
            hours=s.hours,
            amount=s.amount,
            engagement_type=s.engagement_type,
            hourly_rate=s.hourly_rate,
            currency=s.currency,
        )
        for s in rows
    ]


@router.post("/exports/billing/{period_id}", response_model=ErpExportBatchOut)
def export_billing(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ErpExportBatchOut:
    try:
        batch = create_billing_export_batch(
            db, organization_id=user.organization_id, period_id=period_id, author_user_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _batch_out(batch)


@router.post("/exports/payroll/{period_id}", response_model=ErpExportBatchOut)
def export_payroll(
    period_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ErpExportBatchOut:
    try:
        batch = create_payroll_export_batch(
            db, organization_id=user.organization_id, period_id=period_id, author_user_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _batch_out(batch)


@router.get("/exports", response_model=list[ErpExportBatchOut])
def list_exports(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ErpExportBatchOut]:
    rows = list(
        db.scalars(
            select(ErpExportBatch)
            .where(ErpExportBatch.organization_id == user.organization_id)
            .order_by(ErpExportBatch.created_at.desc())
        )
    )
    return [_batch_out(b) for b in rows]


@router.get("/exports/{batch_id}/download")
def download_export(
    batch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    batch = db.scalar(
        select(ErpExportBatch).where(
            ErpExportBatch.id == batch_id, ErpExportBatch.organization_id == user.organization_id
        )
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Export não encontrado")
    return Response(
        content=batch.content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{batch.filename}"'},
    )


@router.post("/exports/{batch_id}/mark-sent", response_model=ErpExportBatchOut)
def export_mark_sent(
    batch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ErpExportBatchOut:
    batch = db.scalar(
        select(ErpExportBatch).where(
            ErpExportBatch.id == batch_id, ErpExportBatch.organization_id == user.organization_id
        )
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Export não encontrado")
    return _batch_out(mark_batch_sent(db, batch))


@router.get("/dashboard/kpis", response_model=DashboardKpisOut)
def dashboard_kpis(
    week_start: date = Query(date(2026, 11, 2)),
    year: int = Query(2026),
    month: int = Query(11),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardKpisOut:
    from datetime import datetime, timedelta, timezone

    from app.services.assignments import unassigned_shifts_in_range

    org_id = user.organization_id
    start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    contracts = db.scalar(select(func.count()).select_from(Contract).where(Contract.organization_id == org_id)) or 0
    employees = db.scalar(select(func.count()).select_from(Employee).where(Employee.organization_id == org_id)) or 0
    shifts_week = db.scalar(
        select(func.count()).select_from(Shift).where(
            Shift.organization_id == org_id, Shift.planned_start >= start, Shift.planned_start < end
        )
    ) or 0
    unassigned = len(unassigned_shifts_in_range(db, organization_id=org_id, start=start, end=end))
    pending = db.scalar(
        select(func.count()).select_from(TimeEntry).where(
            TimeEntry.organization_id == org_id, TimeEntry.status == TimeEntryStatus.SUBMETIDO
        )
    ) or 0
    approved_hours = db.scalar(
        select(func.coalesce(func.sum(TimeEntry.hours_approved), 0)).where(
            TimeEntry.organization_id == org_id, TimeEntry.status == TimeEntryStatus.APROVADO
        )
    ) or 0
    margins = []
    for c in db.scalars(select(Contract).where(Contract.organization_id == org_id, Contract.status == "ATIVO")):
        try:
            m = contract_margin(db, organization_id=org_id, contract_id=c.id, year=year, month=month)
            margins.append(Decimal(m["expected_margin"]))
        except BillingError:
            continue
    exports = db.scalar(
        select(func.count()).select_from(ErpExportBatch).where(ErpExportBatch.organization_id == org_id)
    ) or 0
    alerts = collect_alerts(db, organization_id=org_id, week_start=week_start)
    return DashboardKpisOut(
        contracts=int(contracts),
        employees=int(employees),
        shifts_week=int(shifts_week),
        unassigned_week=unassigned,
        pending_validation=int(pending),
        approved_hours_month=Decimal(str(approved_hours)),
        expected_margin_total=sum(margins, Decimal("0")),
        export_batches=int(exports),
        alerts=len(alerts),
    )


def _get_entry(db: Session, organization_id: uuid.UUID, entry_id: uuid.UUID) -> TimeEntry:
    entry = db.scalar(
        select(TimeEntry)
        .options(joinedload(TimeEntry.shift).joinedload(Shift.store))
        .where(TimeEntry.id == entry_id, TimeEntry.organization_id == organization_id)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Registo de horas não encontrado")
    return entry


def _batch_out(batch: ErpExportBatch) -> ErpExportBatchOut:
    preview = "\n".join(batch.content.splitlines()[:6])
    return ErpExportBatchOut(
        id=batch.id,
        batch_type=batch.batch_type,
        status=batch.status,
        filename=batch.filename,
        row_count=batch.row_count,
        period_label=batch.period_label,
        error_message=batch.error_message,
        created_at=batch.created_at,
        sent_at=batch.sent_at,
        content_preview=preview,
    )
