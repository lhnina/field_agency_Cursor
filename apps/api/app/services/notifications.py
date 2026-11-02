"""In-app notifications + email stub outbox (Q31)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import EmailOutboxStatus, NotificationKind
from app.models import EmailOutbox, Notification


def notify(
    db: Session,
    *,
    organization_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification:
    n = Notification(
        organization_id=organization_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
        read=False,
    )
    db.add(n)
    db.flush()
    return n


def queue_email_stub(
    db: Session,
    *,
    organization_id: uuid.UUID,
    to_address: str,
    subject: str,
    body: str,
    related_kind: str | None = None,
    related_id: str | None = None,
) -> EmailOutbox:
    """No real SMTP — mark SENT_STUB immediately for demo."""
    row = EmailOutbox(
        organization_id=organization_id,
        to_address=to_address,
        subject=subject,
        body=body,
        status=EmailOutboxStatus.SENT_STUB,
        related_kind=related_kind,
        related_id=related_id,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def notify_substitution(
    db: Session,
    *,
    organization_id: uuid.UUID,
    to_email: str | None,
    to_user_id: uuid.UUID | None,
    planned_name: str,
    executed_name: str,
    store_name: str,
    substitution_id: uuid.UUID,
) -> None:
    title = "Substituição registada"
    body = f"{planned_name} → {executed_name} · {store_name}"
    notify(
        db,
        organization_id=organization_id,
        user_id=to_user_id,
        kind=NotificationKind.SUBSTITUICAO,
        title=title,
        body=body,
        entity_type="substitution",
        entity_id=str(substitution_id),
    )
    if to_email:
        queue_email_stub(
            db,
            organization_id=organization_id,
            to_address=to_email,
            subject=f"[FieldOps] {title}",
            body=body,
            related_kind=NotificationKind.SUBSTITUICAO,
            related_id=str(substitution_id),
        )
