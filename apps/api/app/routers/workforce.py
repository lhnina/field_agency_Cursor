"""Absences, documents, substitutions, alerts — PR2 planning ops."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.db import get_db
from app.domain.enums import AbsenceStatus
from app.models import Absence, Employee, EmployeeDocument, Substitution, User
from app.schemas.common import (
    AbsenceCreate,
    AbsenceDecideIn,
    AbsenceOut,
    AlertOut,
    EmployeeDocumentCreate,
    EmployeeDocumentOut,
    SubstitutionOut,
)
from app.services.alerts import collect_alerts

router = APIRouter(tags=["workforce"])


def _absence_out(a: Absence) -> AbsenceOut:
    return AbsenceOut(
        id=a.id,
        organization_id=a.organization_id,
        employee_id=a.employee_id,
        employee_name=a.employee.full_name if a.employee else None,
        absence_type=a.absence_type,
        start_date=a.start_date,
        end_date=a.end_date,
        status=a.status,
        reason=a.reason,
    )


@router.get("/absences", response_model=list[AbsenceOut])
def list_absences(
    status_filter: str | None = Query(None, alias="status"),
    week_start: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AbsenceOut]:
    q = (
        select(Absence)
        .options(joinedload(Absence.employee))
        .where(Absence.organization_id == user.organization_id)
    )
    if status_filter:
        q = q.where(Absence.status == status_filter)
    if week_start:
        week_end = week_start.fromordinal(week_start.toordinal() + 6)
        q = q.where(Absence.start_date <= week_end, Absence.end_date >= week_start)
    rows = list(db.scalars(q.order_by(Absence.start_date.desc())).unique())
    return [_absence_out(a) for a in rows]


@router.post("/absences", response_model=AbsenceOut, status_code=status.HTTP_201_CREATED)
def create_absence(
    payload: AbsenceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AbsenceOut:
    emp = db.scalar(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.organization_id == user.organization_id,
        )
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Data fim anterior à data início")
    absence = Absence(
        organization_id=user.organization_id,
        employee_id=payload.employee_id,
        absence_type=payload.absence_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=AbsenceStatus.PEDIDO,
        reason=payload.reason,
    )
    db.add(absence)
    db.commit()
    absence = db.scalar(
        select(Absence).options(joinedload(Absence.employee)).where(Absence.id == absence.id)
    )
    return _absence_out(absence)  # type: ignore[arg-type]


@router.post("/absences/{absence_id}/decide", response_model=AbsenceOut)
def decide_absence(
    absence_id: uuid.UUID,
    payload: AbsenceDecideIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AbsenceOut:
    if payload.status not in {AbsenceStatus.APROVADO, AbsenceStatus.REJEITADO}:
        raise HTTPException(status_code=400, detail="Estado inválido (APROVADO|REJEITADO)")
    absence = db.scalar(
        select(Absence)
        .options(joinedload(Absence.employee))
        .where(Absence.id == absence_id, Absence.organization_id == user.organization_id)
    )
    if not absence:
        raise HTTPException(status_code=404, detail="Ausência não encontrada")
    absence.status = payload.status
    absence.decided_by_user_id = user.id
    absence.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(absence)
    return _absence_out(absence)


@router.get("/employee-documents", response_model=list[EmployeeDocumentOut])
def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmployeeDocumentOut]:
    rows = list(
        db.scalars(
            select(EmployeeDocument)
            .options(joinedload(EmployeeDocument.employee))
            .where(EmployeeDocument.organization_id == user.organization_id)
            .order_by(EmployeeDocument.expires_on.nulls_last())
        ).unique()
    )
    return [
        EmployeeDocumentOut(
            id=d.id,
            organization_id=d.organization_id,
            employee_id=d.employee_id,
            employee_name=d.employee.full_name if d.employee else None,
            doc_type=d.doc_type,
            label=d.label,
            expires_on=d.expires_on,
            status=d.status,
        )
        for d in rows
    ]


@router.post("/employee-documents", response_model=EmployeeDocumentOut, status_code=201)
def create_document(
    payload: EmployeeDocumentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmployeeDocumentOut:
    emp = db.scalar(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.organization_id == user.organization_id,
        )
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    doc = EmployeeDocument(
        organization_id=user.organization_id,
        **payload.model_dump(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return EmployeeDocumentOut(
        id=doc.id,
        organization_id=doc.organization_id,
        employee_id=doc.employee_id,
        employee_name=emp.full_name,
        doc_type=doc.doc_type,
        label=doc.label,
        expires_on=doc.expires_on,
        status=doc.status,
    )


@router.get("/substitutions", response_model=list[SubstitutionOut])
def list_substitutions(
    shift_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubstitutionOut]:
    q = (
        select(Substitution)
        .options(
            joinedload(Substitution.planned_employee),
            joinedload(Substitution.executed_employee),
        )
        .where(Substitution.organization_id == user.organization_id)
    )
    if shift_id:
        q = q.where(Substitution.shift_id == shift_id)
    rows = list(db.scalars(q.order_by(Substitution.created_at.desc())).unique())
    return [
        SubstitutionOut(
            id=s.id,
            shift_id=s.shift_id,
            planned_employee_id=s.planned_employee_id,
            executed_employee_id=s.executed_employee_id,
            planned_employee_name=s.planned_employee.full_name if s.planned_employee else None,
            executed_employee_name=s.executed_employee.full_name if s.executed_employee else None,
            reason=s.reason,
            absence_id=s.absence_id,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    week_start: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    raw = collect_alerts(db, organization_id=user.organization_id, week_start=week_start)
    return [AlertOut(**item) for item in raw]
