"""PHC export file batch stub — CSV layout with IVA/artigos/CC (Q16–Q18)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import DraftStatus, ExportBatchStatus, ExportBatchType
from app.models import BillingDraft, ErpExportBatch, PayrollPeriod, PayrollStatement
from app.services.payroll import payroll_csv
from app.services.validation import money


def export_billing_csv(drafts: list[BillingDraft]) -> tuple[str, int]:
    """One CSV row per draft line — IT maps to PHC (Q16). Includes IVA, artigo, CC (Q17). EUR 2dp (Q18)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "Cliente",
            "NIF",
            "Contrato",
            "Artigo",
            "Descricao",
            "Quantidade",
            "PrecoUnitario",
            "ValorLiquido",
            "TaxaIVA",
            "ValorIVA",
            "ValorBruto",
            "CentroCusto",
            "Moeda",
            "ModeloFaturacao",
            "ExtraManual",
        ]
    )
    rows = 0
    for draft in drafts:
        client_name = draft.client.name if draft.client else ""
        nif = draft.client.vat_number if draft.client else ""
        for line in draft.lines:
            line_vat = money(line.line_net * (draft.vat_rate / money(100)))
            writer.writerow(
                [
                    client_name,
                    nif or "",
                    str(draft.contract_id or ""),
                    line.article_code,
                    line.description,
                    f"{money(line.quantity):.2f}",
                    f"{money(line.unit_price):.2f}",
                    f"{money(line.line_net):.2f}",
                    f"{money(draft.vat_rate):.2f}",
                    f"{line_vat:.2f}",
                    f"{money(line.line_net + line_vat):.2f}",
                    line.cost_center or draft.cost_center or "",
                    draft.currency,
                    line.billing_model,
                    "S" if line.extra_override else "N",
                ]
            )
            rows += 1
    return buf.getvalue(), rows


def create_billing_export_batch(
    db: Session,
    *,
    organization_id: uuid.UUID,
    period_id: uuid.UUID,
    author_user_id: uuid.UUID | None = None,
) -> ErpExportBatch:
    drafts = list(
        db.scalars(
            select(BillingDraft)
            .options(joinedload(BillingDraft.lines), joinedload(BillingDraft.client))
            .where(
                BillingDraft.organization_id == organization_id,
                BillingDraft.period_id == period_id,
            )
        ).unique()
    )
    if not drafts:
        raise ValueError("Sem pré-faturas para exportar")

    content, rows = export_billing_csv(drafts)
    filename = f"phc_faturacao_{period_id}.csv"
    batch = ErpExportBatch(
        organization_id=organization_id,
        batch_type=ExportBatchType.FATURACAO,
        status=ExportBatchStatus.PENDING,
        filename=filename,
        content=content,
        row_count=rows,
        period_label=str(period_id),
        created_by_user_id=author_user_id,
    )
    db.add(batch)
    for d in drafts:
        d.status = DraftStatus.EXPORTADO
    db.commit()
    db.refresh(batch)
    return batch


def create_payroll_export_batch(
    db: Session,
    *,
    organization_id: uuid.UUID,
    period_id: uuid.UUID,
    author_user_id: uuid.UUID | None = None,
    engagement_type: str | None = None,
) -> ErpExportBatch:
    period = db.get(PayrollPeriod, period_id)
    if not period or period.organization_id != organization_id:
        raise ValueError("Período de apuramento não encontrado")
    q = (
        select(PayrollStatement)
        .options(joinedload(PayrollStatement.employee))
        .where(PayrollStatement.period_id == period_id)
    )
    if engagement_type:
        q = q.where(PayrollStatement.engagement_type == engagement_type)
    statements = list(db.scalars(q).unique())
    if not statements:
        raise ValueError("Sem linhas de apuramento")

    suffix = f"_{engagement_type}" if engagement_type else ""
    content = payroll_csv(statements)
    batch = ErpExportBatch(
        organization_id=organization_id,
        batch_type=ExportBatchType.REMUNERACAO,
        status=ExportBatchStatus.PENDING,
        filename=f"phc_remuneracao_{period.year}_{period.month:02d}{suffix}.csv",
        content=content,
        row_count=len(statements),
        period_label=f"{period.year}-{period.month:02d}{suffix}",
        created_by_user_id=author_user_id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def mark_batch_sent(db: Session, batch: ErpExportBatch) -> ErpExportBatch:
    batch.status = ExportBatchStatus.SENT
    batch.sent_at = datetime.now(timezone.utc)
    batch.error_message = None
    db.commit()
    db.refresh(batch)
    return batch


def mark_batch_acked(
    db: Session,
    batch: ErpExportBatch,
    *,
    ack_reference: str | None = None,
) -> ErpExportBatch:
    batch.status = ExportBatchStatus.ACKED
    batch.acked_at = datetime.now(timezone.utc)
    batch.ack_reference = ack_reference
    batch.error_message = None
    db.commit()
    db.refresh(batch)
    return batch


def mark_batch_error(
    db: Session,
    batch: ErpExportBatch,
    *,
    error_message: str,
) -> ErpExportBatch:
    batch.status = ExportBatchStatus.ERROR
    batch.error_message = error_message[:255]
    db.commit()
    db.refresh(batch)
    return batch


def retry_batch(db: Session, batch: ErpExportBatch) -> ErpExportBatch:
    """Reset ERROR/PENDING to SENT for retry (re-queue stub)."""
    if batch.status not in {ExportBatchStatus.ERROR, ExportBatchStatus.PENDING, ExportBatchStatus.SENT}:
        raise ValueError("Só batches PENDING/SENT/ERROR podem ser retentados")
    batch.retry_count = (batch.retry_count or 0) + 1
    batch.status = ExportBatchStatus.SENT
    batch.sent_at = datetime.now(timezone.utc)
    batch.error_message = None
    db.commit()
    db.refresh(batch)
    return batch
