from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    organization_id: uuid.UUID
    roles: list[str] = []


class OrganizationCreate(BaseModel):
    name: str
    timezone: str = "Europe/Lisbon"
    settings: dict = Field(default_factory=dict)


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    timezone: str
    settings: dict


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    settings: Optional[dict] = None


class ClientCreate(BaseModel):
    name: str
    vat_number: Optional[str] = None
    status: str = "ATIVO"


class ClientOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    vat_number: Optional[str]
    status: str


class BrandCreate(BaseModel):
    client_id: uuid.UUID
    name: str


class BrandOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    name: str


class RetailChainCreate(BaseModel):
    name: str
    insignia: Optional[str] = None


class RetailChainOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    insignia: Optional[str]


class StoreCreate(BaseModel):
    retail_chain_id: uuid.UUID
    name: str
    credential_name: Optional[str] = None
    address: Optional[str] = None
    zone_code: str = "AML Norte"
    agency_supervisor_id: Optional[uuid.UUID] = None
    opening_hours: dict = Field(default_factory=dict)


class StoreOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    retail_chain_id: uuid.UUID
    name: str
    credential_name: Optional[str]
    address: Optional[str]
    zone_code: str
    agency_supervisor_id: Optional[uuid.UUID]


class EmployeeCreate(BaseModel):
    full_name: str
    engagement_type: str = "CT"
    zone_code: str = "AML Norte"
    supervisor_id: Optional[uuid.UUID] = None
    status: str = "ATIVO"
    hourly_cost: Optional[Decimal] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    availability: dict = Field(default_factory=dict)


class EmployeeOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    full_name: str
    engagement_type: str
    zone_code: str
    supervisor_id: Optional[uuid.UUID]
    status: str
    hourly_cost: Optional[Decimal]
    email: Optional[str]
    phone: Optional[str]


class ContractLineCreate(BaseModel):
    store_id: uuid.UUID
    service_type: str
    contracted_hours: Optional[Decimal] = None
    bill_rate: Optional[Decimal] = None
    fixed_amount: Optional[Decimal] = None
    schedule_rules: dict = Field(default_factory=dict)
    pricing_components: dict = Field(default_factory=dict)
    start_date: date
    end_date: Optional[date] = None
    generates_daily_shifts: bool = True


class ContractLineOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contract_id: uuid.UUID
    store_id: uuid.UUID
    service_type: str
    contracted_hours: Optional[Decimal]
    bill_rate: Optional[Decimal]
    fixed_amount: Optional[Decimal]
    schedule_rules: Optional[dict]
    pricing_components: Optional[dict]
    start_date: date
    end_date: Optional[date]
    generates_daily_shifts: bool


class ContractCreate(BaseModel):
    client_id: uuid.UUID
    brand_id: Optional[uuid.UUID] = None
    number: str
    type: str
    start_date: date
    end_date: Optional[date] = None
    status: str = "ATIVO"
    notes: Optional[str] = None
    lines: list[ContractLineCreate] = Field(default_factory=list)


class ContractOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    number: str
    type: str
    billing_model: str
    start_date: date
    end_date: Optional[date]
    status: str
    version: int
    notes: Optional[str]
    lines: list[ContractLineOut] = []


class ContractVersionOut(ORMModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    version: int
    reason: Optional[str]
    created_at: datetime
    snapshot: dict


class ServicePlanCreate(BaseModel):
    contract_line_id: uuid.UUID
    name: str
    recurrence_rule: dict
    default_employee_id: Optional[uuid.UUID] = None


class ServicePlanOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contract_line_id: uuid.UUID
    name: str
    recurrence_rule: dict
    default_employee_id: Optional[uuid.UUID]
    active: bool


class GenerateShiftsIn(BaseModel):
    service_plan_id: uuid.UUID
    week_start: date


class AssignmentOut(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    is_substitute: bool
    active: bool


class ShiftOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contract_line_id: uuid.UUID
    service_plan_id: Optional[uuid.UUID]
    store_id: uuid.UUID
    store_name: Optional[str] = None
    planned_start: datetime
    planned_end: datetime
    status: str
    shift_type: str
    assignments: list[AssignmentOut] = []


class TimeEntryOut(ORMModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    hours_contracted: Decimal
    hours_planned: Decimal
    hours_assigned: Decimal
    hours_executed: Decimal
    hours_approved: Decimal
    hours_billable: Decimal
    hours_payable: Decimal
    status: str


class PlanningWeekOut(BaseModel):
    week_start: date
    week_end: date
    shifts: list[ShiftOut]
    employees: list[EmployeeOut]
    absences: list["AbsenceOut"] = []
    unassigned_count: int = 0


class RoleOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: Optional[str]


class AssignShiftIn(BaseModel):
    employee_id: uuid.UUID
    set_as_stable_default: bool = False
    allow_overlap_override: bool = False


class StableAssigneeIn(BaseModel):
    default_employee_id: Optional[uuid.UUID] = None


class SubstituteIn(BaseModel):
    substitute_employee_id: uuid.UUID
    reason: Optional[str] = None
    absence_id: Optional[uuid.UUID] = None
    allow_overlap_override: bool = False


class SubstitutionOut(ORMModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    planned_employee_id: uuid.UUID
    executed_employee_id: uuid.UUID
    planned_employee_name: Optional[str] = None
    executed_employee_name: Optional[str] = None
    reason: Optional[str]
    absence_id: Optional[uuid.UUID]
    created_at: datetime


class AbsenceCreate(BaseModel):
    employee_id: uuid.UUID
    absence_type: str
    start_date: date
    end_date: date
    reason: Optional[str] = None


class AbsenceDecideIn(BaseModel):
    status: str  # APROVADO | REJEITADO


class AbsenceOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    absence_type: str
    start_date: date
    end_date: date
    status: str
    reason: Optional[str]


class EmployeeDocumentCreate(BaseModel):
    employee_id: uuid.UUID
    doc_type: str
    label: Optional[str] = None
    expires_on: Optional[date] = None
    status: str = "VALIDO"


class EmployeeDocumentOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    doc_type: str
    label: Optional[str]
    expires_on: Optional[date]
    status: str


class AlertOut(BaseModel):
    kind: str
    severity: str
    title: str
    message: str
    entity_type: str
    entity_id: str
