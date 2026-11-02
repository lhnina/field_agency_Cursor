from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# JSON that works on Postgres (JSONB) and SQLite fallback for local smoke tests
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Lisbon")
    settings: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    clients: Mapped[list[Client]] = relationship(back_populates="organization")
    employees: Mapped[list[Employee]] = relationship(back_populates="organization")
    users: Mapped[list[User]] = relationship(back_populates="organization")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id"), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="users")
    roles: Mapped[list[UserRole]] = relationship(back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("organization_id", "vat_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vat_number: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="ATIVO")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="clients")
    brands: Mapped[list[Brand]] = relationship(back_populates="client")
    contracts: Mapped[list[Contract]] = relationship(back_populates="client")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    client: Mapped[Client] = relationship(back_populates="brands")


class RetailChain(Base):
    __tablename__ = "retail_chains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    insignia: Mapped[Optional[str]] = mapped_column(String(120))

    stores: Mapped[list[Store]] = relationship(back_populates="retail_chain")


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    retail_chain_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retail_chains.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_name: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(String(400))
    geo_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    geo_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    zone_code: Mapped[str] = mapped_column(String(64), nullable=False, default="AML Norte")
    agency_supervisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    opening_hours: Mapped[Optional[dict]] = mapped_column(JsonType, default=dict)

    retail_chain: Mapped[RetailChain] = relationship(back_populates="stores")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    engagement_type: Mapped[str] = mapped_column(String(16), default="CT")
    zone_code: Mapped[str] = mapped_column(String(64), default="AML Norte")
    supervisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ATIVO")
    hourly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    availability: Mapped[Optional[dict]] = mapped_column(JsonType, default=dict)

    organization: Mapped[Organization] = relationship(back_populates="employees")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("brands.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_model: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="ATIVO")
    version: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    client: Mapped[Client] = relationship(back_populates="contracts")
    lines: Mapped[list[ContractLine]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    versions: Mapped[list[ContractVersion]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class ContractVersion(Base):
    """Immutable snapshot stub for contract versioning."""

    __tablename__ = "contract_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JsonType, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    author_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="versions")


class ContractLine(Base):
    __tablename__ = "contract_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"), nullable=False, index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contracted_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    bill_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    fixed_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    schedule_rules: Mapped[Optional[dict]] = mapped_column(JsonType, default=dict)
    pricing_components: Mapped[Optional[dict]] = mapped_column(JsonType, default=dict)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    # Equipas fixas: monthly billing, no daily shifts in MVP (Q06)
    generates_daily_shifts: Mapped[bool] = mapped_column(Boolean, default=True)

    contract: Mapped[Contract] = relationship(back_populates="lines")
    store: Mapped[Store] = relationship()
    service_plans: Mapped[list[ServicePlan]] = relationship(back_populates="contract_line")


class ServicePlan(Base):
    __tablename__ = "service_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    contract_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_lines.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    recurrence_rule: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    # Stable assignment at planning level (Q04)
    default_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    contract_line: Mapped[ContractLine] = relationship(back_populates="service_plans")
    shifts: Mapped[list[Shift]] = relationship(back_populates="service_plan")


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    contract_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_lines.id"), nullable=False, index=True)
    service_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("service_plans.id"), nullable=True)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PLANEADO")
    shift_type: Mapped[str] = mapped_column(String(32), nullable=False)

    service_plan: Mapped[Optional[ServicePlan]] = relationship(back_populates="shifts")
    store: Mapped[Store] = relationship()
    assignments: Mapped[list[Assignment]] = relationship(back_populates="shift", cascade="all, delete-orphan")
    time_entries: Mapped[list[TimeEntry]] = relationship(back_populates="shift", cascade="all, delete-orphan")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), default="EXECUTOR")
    is_substitute: Mapped[bool] = mapped_column(Boolean, default=False)
    replaces_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    shift: Mapped[Shift] = relationship(back_populates="assignments")
    employee: Mapped[Employee] = relationship()


class TimeEntry(Base):
    """Tracks the 7 hour concepts for a shift/period line."""

    __tablename__ = "time_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    hours_contracted: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_planned: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_assigned: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_executed: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_approved: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_billable: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    hours_payable: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="RASCUNHO")

    shift: Mapped[Shift] = relationship(back_populates="time_entries")
    history: Mapped[list[TimeStateHistory]] = relationship(back_populates="time_entry", cascade="all, delete-orphan")


class TimeStateHistory(Base):
    __tablename__ = "time_state_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    time_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("time_entries.id"), nullable=False, index=True)
    concept: Mapped[str] = mapped_column(String(32), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    author_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    time_entry: Mapped[TimeEntry] = relationship(back_populates="history")


class Absence(Base):
    """Leave / unavailability — approvals minimal (MVP-15). Equipas fixas use absences (Q06)."""

    __tablename__ = "absences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    absence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PEDIDO")
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    decided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship()


class EmployeeDocument(Base):
    """Collaborator documents with expiry — alerts only in MVP (MVP-07)."""

    __tablename__ = "employee_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(200))
    expires_on: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="VALIDO")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Employee] = relationship()


class Substitution(Base):
    """Planned vs executed history for a shift replacement (MVP-16 stub)."""

    __tablename__ = "substitutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    planned_employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    executed_employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    original_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("assignments.id"))
    new_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("assignments.id"))
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    absence_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("absences.id"))
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    shift: Mapped[Shift] = relationship()
    planned_employee: Mapped[Employee] = relationship(foreign_keys=[planned_employee_id])
    executed_employee: Mapped[Employee] = relationship(foreign_keys=[executed_employee_id])
