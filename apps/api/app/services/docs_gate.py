"""Configurable soft-block of expired docs on assignment (REC-07)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import DocumentStatus
from app.models import EmployeeDocument, Organization


def org_soft_block_docs(db: Session, organization_id: uuid.UUID) -> bool:
    org = db.get(Organization, organization_id)
    if not org or not isinstance(org.settings, dict):
        return False
    return bool(org.settings.get("soft_block_docs_on_assign", False))


def expired_docs_for_employee(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_id: uuid.UUID,
    on_day: date | None = None,
) -> list[EmployeeDocument]:
    on_day = on_day or date.today()
    docs = list(
        db.scalars(
            select(EmployeeDocument).where(
                EmployeeDocument.organization_id == organization_id,
                EmployeeDocument.employee_id == employee_id,
            )
        )
    )
    expired = []
    for d in docs:
        if d.expires_on and d.expires_on < on_day:
            d.status = DocumentStatus.EXPIRADO
            expired.append(d)
        elif d.status == DocumentStatus.EXPIRADO:
            expired.append(d)
    return expired


class DocsSoftBlockError(Exception):
    def __init__(self, message: str, doc_ids: list[uuid.UUID]):
        super().__init__(message)
        self.doc_ids = doc_ids
