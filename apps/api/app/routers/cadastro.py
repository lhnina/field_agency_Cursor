from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Brand, Client, Employee, Organization, RetailChain, Store, User
from app.schemas.common import (
    BrandCreate,
    BrandOut,
    ClientCreate,
    ClientOut,
    EmployeeCreate,
    EmployeeOut,
    OrganizationOut,
    OrganizationUpdate,
    RetailChainCreate,
    RetailChainOut,
    StoreCreate,
    StoreOut,
)

router = APIRouter(tags=["cadastro"])


@router.get("/organization", response_model=OrganizationOut)
def get_organization(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Organization:
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    return org


@router.patch("/organization", response_model=OrganizationOut)
def update_organization(
    payload: OrganizationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org


@router.get("/clients", response_model=list[ClientOut])
def list_clients(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Client]:
    return list(db.scalars(select(Client).where(Client.organization_id == user.organization_id).order_by(Client.name)))


@router.post("/clients", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Client:
    client = Client(organization_id=user.organization_id, **payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/brands", response_model=list[BrandOut])
def list_brands(
    client_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Brand]:
    q = select(Brand).where(Brand.organization_id == user.organization_id)
    if client_id:
        q = q.where(Brand.client_id == client_id)
    return list(db.scalars(q.order_by(Brand.name)))


@router.post("/brands", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Brand:
    client = db.scalar(
        select(Client).where(Client.id == payload.client_id, Client.organization_id == user.organization_id)
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    brand = Brand(organization_id=user.organization_id, client_id=payload.client_id, name=payload.name)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/retail-chains", response_model=list[RetailChainOut])
def list_chains(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RetailChain]:
    return list(
        db.scalars(
            select(RetailChain).where(RetailChain.organization_id == user.organization_id).order_by(RetailChain.name)
        )
    )


@router.post("/retail-chains", response_model=RetailChainOut, status_code=status.HTTP_201_CREATED)
def create_chain(
    payload: RetailChainCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetailChain:
    chain = RetailChain(organization_id=user.organization_id, **payload.model_dump())
    db.add(chain)
    db.commit()
    db.refresh(chain)
    return chain


@router.get("/stores", response_model=list[StoreOut])
def list_stores(
    retail_chain_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Store]:
    q = select(Store).where(Store.organization_id == user.organization_id)
    if retail_chain_id:
        q = q.where(Store.retail_chain_id == retail_chain_id)
    return list(db.scalars(q.order_by(Store.name)))


@router.post("/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: StoreCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Store:
    chain = db.scalar(
        select(RetailChain).where(
            RetailChain.id == payload.retail_chain_id,
            RetailChain.organization_id == user.organization_id,
        )
    )
    if not chain:
        raise HTTPException(status_code=404, detail="Cadeia não encontrada")
    store = Store(organization_id=user.organization_id, **payload.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Employee]:
    return list(
        db.scalars(select(Employee).where(Employee.organization_id == user.organization_id).order_by(Employee.full_name))
    )


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Employee:
    employee = Employee(organization_id=user.organization_id, **payload.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.organization_id == user.organization_id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    return employee
