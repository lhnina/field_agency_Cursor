from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Brand, Client, Contract, ContractLine, ContractVersion, Store, User
from app.schemas.common import (
    ContractCreate,
    ContractLineCreate,
    ContractLineOut,
    ContractOut,
    ContractVersionOut,
)
from app.services.billing import billing_model_for, line_generates_daily_shifts

router = APIRouter(prefix="/contracts", tags=["contratos"])


def _snapshot(contract: Contract) -> dict:
    return {
        "number": contract.number,
        "type": contract.type,
        "billing_model": contract.billing_model,
        "status": contract.status,
        "version": contract.version,
        "start_date": str(contract.start_date),
        "end_date": str(contract.end_date) if contract.end_date else None,
        "notes": contract.notes,
        "lines": [
            {
                "id": str(line.id),
                "store_id": str(line.store_id),
                "service_type": line.service_type,
                "contracted_hours": str(line.contracted_hours) if line.contracted_hours is not None else None,
                "bill_rate": str(line.bill_rate) if line.bill_rate is not None else None,
                "fixed_amount": str(line.fixed_amount) if line.fixed_amount is not None else None,
                "generates_daily_shifts": line.generates_daily_shifts,
            }
            for line in contract.lines
        ],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("", response_model=list[ContractOut])
def list_contracts(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Contract]:
    return list(
        db.scalars(
            select(Contract)
            .options(joinedload(Contract.lines))
            .where(Contract.organization_id == user.organization_id)
            .order_by(Contract.number)
        ).unique()
    )


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Contract:
    client = db.scalar(
        select(Client).where(Client.id == payload.client_id, Client.organization_id == user.organization_id)
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if payload.brand_id:
        brand = db.scalar(
            select(Brand).where(Brand.id == payload.brand_id, Brand.organization_id == user.organization_id)
        )
        if not brand:
            raise HTTPException(status_code=404, detail="Marca não encontrada")

    contract = Contract(
        organization_id=user.organization_id,
        client_id=payload.client_id,
        brand_id=payload.brand_id,
        number=payload.number,
        type=payload.type,
        billing_model=billing_model_for(payload.type),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
        version=1,
        notes=payload.notes,
    )
    db.add(contract)
    db.flush()

    for line_in in payload.lines:
        store = db.scalar(
            select(Store).where(Store.id == line_in.store_id, Store.organization_id == user.organization_id)
        )
        if not store:
            raise HTTPException(status_code=404, detail=f"Loja {line_in.store_id} não encontrada")
        generates = (
            line_in.generates_daily_shifts
            if "generates_daily_shifts" in line_in.model_fields_set
            else line_generates_daily_shifts(payload.type)
        )
        db.add(
            ContractLine(
                organization_id=user.organization_id,
                contract_id=contract.id,
                store_id=line_in.store_id,
                service_type=line_in.service_type or payload.type,
                contracted_hours=line_in.contracted_hours,
                bill_rate=line_in.bill_rate,
                fixed_amount=line_in.fixed_amount,
                schedule_rules=line_in.schedule_rules,
                pricing_components=line_in.pricing_components,
                start_date=line_in.start_date,
                end_date=line_in.end_date,
                generates_daily_shifts=generates,
            )
        )

    db.flush()
    db.refresh(contract)
    db.add(
        ContractVersion(
            organization_id=user.organization_id,
            contract_id=contract.id,
            version=contract.version,
            snapshot=_snapshot(contract),
            reason="Criação inicial",
            author_user_id=user.id,
        )
    )
    db.commit()
    return db.scalar(
        select(Contract).options(joinedload(Contract.lines)).where(Contract.id == contract.id)
    )  # type: ignore[return-value]


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Contract:
    contract = db.scalar(
        select(Contract)
        .options(joinedload(Contract.lines))
        .where(Contract.id == contract_id, Contract.organization_id == user.organization_id)
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return contract


@router.post("/{contract_id}/lines", response_model=ContractLineOut, status_code=status.HTTP_201_CREATED)
def add_line(
    contract_id: uuid.UUID,
    payload: ContractLineCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContractLine:
    contract = db.scalar(
        select(Contract)
        .options(joinedload(Contract.lines))
        .where(Contract.id == contract_id, Contract.organization_id == user.organization_id)
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    generates = (
        payload.generates_daily_shifts
        if "generates_daily_shifts" in payload.model_fields_set
        else line_generates_daily_shifts(contract.type)
    )
    line = ContractLine(
        organization_id=user.organization_id,
        contract_id=contract.id,
        store_id=payload.store_id,
        service_type=payload.service_type,
        contracted_hours=payload.contracted_hours,
        bill_rate=payload.bill_rate,
        fixed_amount=payload.fixed_amount,
        schedule_rules=payload.schedule_rules,
        pricing_components=payload.pricing_components,
        start_date=payload.start_date,
        end_date=payload.end_date,
        generates_daily_shifts=generates,
    )
    db.add(line)
    contract.version += 1
    db.flush()
    db.add(
        ContractVersion(
            organization_id=user.organization_id,
            contract_id=contract.id,
            version=contract.version,
            snapshot=_snapshot(contract),
            reason="Nova linha de contrato",
            author_user_id=user.id,
        )
    )
    db.commit()
    db.refresh(line)
    return line


@router.get("/{contract_id}/versions", response_model=list[ContractVersionOut])
def list_versions(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContractVersion]:
    contract = db.scalar(
        select(Contract).where(Contract.id == contract_id, Contract.organization_id == user.organization_id)
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return list(
        db.scalars(
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .order_by(ContractVersion.version.desc())
        )
    )
