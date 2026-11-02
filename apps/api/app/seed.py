"""Seed demo PT-PT data + 7 RBAC profiles."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.domain.enums import AbsenceStatus, AbsenceType, ContractType, DocumentStatus, RoleCode
from app.models import (
    Absence,
    Brand,
    Client,
    Contract,
    ContractLine,
    ContractVersion,
    Employee,
    EmployeeDocument,
    Organization,
    Permission,
    RetailChain,
    Role,
    RolePermission,
    ServicePlan,
    Store,
    User,
    UserRole,
)
from app.services.billing import billing_model_for, line_generates_daily_shifts
from app.services.shifts import generate_shifts_for_week

ROLES = [
    (RoleCode.ADMINISTRADOR, "Administrador", "Acesso total"),
    (RoleCode.DIRECAO, "Direção", "Visão executiva e KPIs"),
    (RoleCode.GESTOR_OPERACIONAL, "Gestor operacional", "Planeamento e contratos"),
    (RoleCode.SUPERVISOR, "Supervisor", "Validação de horas e equipa"),
    (RoleCode.RH, "RH", "Colaboradores e apuramento"),
    (RoleCode.FINANCEIRO, "Financeiro", "Pré-faturação e export"),
    (RoleCode.COLABORADOR, "Colaborador", "Portal / escala própria"),
]

PERMISSIONS = [
    ("org.read", "Ler organização"),
    ("org.write", "Editar organização"),
    ("clients.write", "Gerir clientes"),
    ("employees.write", "Gerir colaboradores"),
    ("contracts.write", "Gerir contratos"),
    ("planning.write", "Gerir planeamento"),
    ("hours.validate", "Validar horas"),
    ("billing.write", "Pré-faturação"),
]


def seed_if_empty(db: Session) -> None:
    existing = db.scalar(select(Organization).limit(1))
    if existing:
        return
    seed_all(db)


def seed_all(db: Session) -> Organization:
    org = Organization(
        name="FieldOps Demo PT",
        timezone="Europe/Lisbon",
        settings={
            "currency": "EUR",
            "billing_cap": "contracted",  # Q11
            "auto_approve_business_days": 3,  # Q12
            "ct_mode": "alerts_only",  # Q20
            "locale": "pt-PT",
        },
    )
    db.add(org)
    db.flush()

    role_by_code: dict[str, Role] = {}
    for code, name, desc in ROLES:
        role = Role(code=code, name=name, description=desc)
        db.add(role)
        db.flush()
        role_by_code[code] = role

    perm_by_code: dict[str, Permission] = {}
    for code, desc in PERMISSIONS:
        perm = Permission(code=code, description=desc)
        db.add(perm)
        db.flush()
        perm_by_code[code] = perm

    # Admin gets all; others get a subset stub
    for code, role in role_by_code.items():
        codes = list(perm_by_code.keys()) if code == RoleCode.ADMINISTRADOR else ["org.read", "planning.write"]
        if code == RoleCode.FINANCEIRO:
            codes = ["org.read", "billing.write"]
        if code == RoleCode.RH:
            codes = ["org.read", "employees.write"]
        if code == RoleCode.SUPERVISOR:
            codes = ["org.read", "hours.validate", "planning.write"]
        for pcode in codes:
            db.add(RolePermission(role_id=role.id, permission_id=perm_by_code[pcode].id))

    # Employees first (for supervisor refs)
    ana = Employee(
        organization_id=org.id,
        full_name="Ana Sousa",
        engagement_type="CT",
        zone_code="AML Norte",
        hourly_cost=Decimal("9.50"),
        email="ana.sousa@demo.fieldops.pt",
        status="ATIVO",
    )
    bruno = Employee(
        organization_id=org.id,
        full_name="Bruno Martins",
        engagement_type="RV",
        zone_code="AML Sul",
        hourly_cost=Decimal("11.00"),
        email="bruno.martins@demo.fieldops.pt",
        status="ATIVO",
    )
    carla = Employee(
        organization_id=org.id,
        full_name="Carla Ferreira",
        engagement_type="CT",
        zone_code="AML Norte",
        hourly_cost=Decimal("9.80"),
        email="carla.ferreira@demo.fieldops.pt",
        status="ATIVO",
    )
    diogo = Employee(
        organization_id=org.id,
        full_name="Diogo Pereira",
        engagement_type="CT",
        zone_code="Grande Porto",
        hourly_cost=Decimal("9.20"),
        email="diogo.pereira@demo.fieldops.pt",
        status="ATIVO",
    )
    ines = Employee(
        organization_id=org.id,
        full_name="Inês Rocha",
        engagement_type="CT",
        zone_code="AML Sul",
        hourly_cost=Decimal("9.40"),
        email="ines.rocha@demo.fieldops.pt",
        status="ATIVO",
    )
    db.add_all([ana, bruno, carla, diogo, ines])
    db.flush()
    carla.supervisor_id = ana.id
    diogo.supervisor_id = ana.id

    # Back-office users (demo password: fieldops)
    demo_password = hash_password("fieldops")
    admin = User(
        organization_id=org.id,
        email="admin@fieldops.pt",
        full_name="Luis Admin",
        hashed_password=demo_password,
        is_active=True,
    )
    gestor = User(
        organization_id=org.id,
        email="gestor@fieldops.pt",
        full_name="Marta Gestora",
        hashed_password=demo_password,
        is_active=True,
    )
    db.add_all([admin, gestor])
    db.flush()
    db.add(UserRole(user_id=admin.id, role_id=role_by_code[RoleCode.ADMINISTRADOR].id))
    db.add(UserRole(user_id=gestor.id, role_id=role_by_code[RoleCode.GESTOR_OPERACIONAL].id))

    # Seed users for remaining profiles (loginable stubs)
    for code, email, name in [
        (RoleCode.DIRECAO, "direcao@fieldops.pt", "Rita Direção"),
        (RoleCode.SUPERVISOR, "supervisor@fieldops.pt", "Paulo Supervisor"),
        (RoleCode.RH, "rh@fieldops.pt", "Sofia RH"),
        (RoleCode.FINANCEIRO, "fin@fieldops.pt", "Tiago Financeiro"),
        (RoleCode.COLABORADOR, "ana.sousa@demo.fieldops.pt", "Ana Sousa"),
    ]:
        u = User(
            organization_id=org.id,
            email=email,
            full_name=name,
            hashed_password=demo_password,
            is_active=True,
            employee_id=ana.id if code == RoleCode.COLABORADOR else None,
        )
        db.add(u)
        db.flush()
        db.add(UserRole(user_id=u.id, role_id=role_by_code[code].id))

    # Commercial cadastro
    client_x = Client(organization_id=org.id, name="Cliente X", vat_number="500100200", status="ATIVO")
    client_z = Client(organization_id=org.id, name="Cliente Z", vat_number="500300400", status="ATIVO")
    client_h = Client(organization_id=org.id, name="Cliente H", vat_number="500500600", status="ATIVO")
    db.add_all([client_x, client_z, client_h])
    db.flush()

    brand_abc = Brand(organization_id=org.id, client_id=client_x.id, name="Marca ABC")
    brand_xpt = Brand(organization_id=org.id, client_id=client_z.id, name="XPT")
    brand_op = Brand(organization_id=org.id, client_id=client_h.id, name="OP")
    db.add_all([brand_abc, brand_xpt, brand_op])
    db.flush()

    continente = RetailChain(organization_id=org.id, name="Continente", insignia="Continente")
    pingo = RetailChain(organization_id=org.id, name="Pingo Doce", insignia="Pingo Doce")
    auchan = RetailChain(organization_id=org.id, name="Auchan", insignia="Auchan")
    db.add_all([continente, pingo, auchan])
    db.flush()

    stores = [
        Store(
            organization_id=org.id,
            retail_chain_id=continente.id,
            name="Continente Amadora",
            credential_name="Amadora",
            address="Amadora",
            zone_code="AML Norte",
            agency_supervisor_id=ana.id,
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=continente.id,
            name="Continente Cascais",
            credential_name="Cascais",
            address="Cascais",
            zone_code="AML Sul",
            agency_supervisor_id=ana.id,
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=continente.id,
            name="Continente Matosinhos",
            credential_name="Matosinhos",
            address="Matosinhos",
            zone_code="Grande Porto",
            agency_supervisor_id=ana.id,
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=continente.id,
            name="Continente Gaia",
            credential_name="Gaia",
            address="Vila Nova de Gaia",
            zone_code="Grande Porto",
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=continente.id,
            name="Continente Colombo",
            credential_name="Colombo",
            address="Lisboa",
            zone_code="AML Norte",
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=pingo.id,
            name="Pingo Doce Chiado",
            credential_name="Chiado",
            address="Lisboa",
            zone_code="AML Norte",
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=pingo.id,
            name="Pingo Doce Almada",
            credential_name="Almada",
            address="Almada",
            zone_code="AML Sul",
        ),
        Store(
            organization_id=org.id,
            retail_chain_id=auchan.id,
            name="Auchan Alfragide",
            credential_name="Alfragide",
            address="Alfragide",
            zone_code="AML Norte",
        ),
    ]
    db.add_all(stores)
    db.flush()
    by_name = {s.name: s for s in stores}

    # Contracts
    today = date(2026, 11, 2)
    week_start = date(2026, 11, 2)  # Monday of week 45

    c_rep = Contract(
        organization_id=org.id,
        client_id=client_x.id,
        brand_id=brand_abc.id,
        number="CT-REP-2026-001",
        type=ContractType.REPOSICAO,
        billing_model=billing_model_for(ContractType.REPOSICAO),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="ATIVO",
        version=1,
        notes="Reposição semanal multi-loja",
    )
    c_prom = Contract(
        organization_id=org.id,
        client_id=client_z.id,
        brand_id=brand_xpt.id,
        number="CT-PROM-2026-014",
        type=ContractType.PROMOCAO,
        billing_model=billing_model_for(ContractType.PROMOCAO),
        start_date=date(2026, 10, 1),
        end_date=date(2026, 11, 30),
        status="ATIVO",
        version=1,
    )
    c_log = Contract(
        organization_id=org.id,
        client_id=client_h.id,
        brand_id=brand_op.id,
        number="CT-LOG-2026-003",
        type=ContractType.LOGISTICA,
        billing_model=billing_model_for(ContractType.LOGISTICA),
        start_date=date(2026, 9, 1),
        status="ATIVO",
        version=1,
    )
    c_eq = Contract(
        organization_id=org.id,
        client_id=client_x.id,
        brand_id=brand_abc.id,
        number="CT-EQ-2026-002",
        type=ContractType.EQUIPAS_FIXAS,
        billing_model=billing_model_for(ContractType.EQUIPAS_FIXAS),
        start_date=date(2026, 1, 1),
        status="ATIVO",
        version=1,
        notes="Equipas fixas — faturação mensal, sem turnos diários",
    )
    db.add_all([c_rep, c_prom, c_log, c_eq])
    db.flush()

    lines_spec = [
        (
            c_rep,
            by_name["Continente Amadora"],
            Decimal("3"),
            Decimal("18.00"),
            None,
            {"weekdays": ["mon", "wed"], "start_time": "09:00", "end_time": "12:00"},
            {},
            ana,
            "Plano Rep Amadora",
        ),
        (
            c_rep,
            by_name["Continente Cascais"],
            Decimal("3"),
            Decimal("18.00"),
            None,
            {"weekdays": ["mon", "thu"], "start_time": "09:00", "end_time": "12:00"},
            {},
            None,
            "Plano Rep Cascais",
        ),
        (
            c_rep,
            by_name["Continente Matosinhos"],
            Decimal("3"),
            Decimal("17.50"),
            None,
            {"weekdays": ["mon", "wed"], "start_time": "08:00", "end_time": "11:00"},
            {},
            diogo,
            "Plano Rep Matosinhos",
        ),
        (
            c_rep,
            by_name["Continente Gaia"],
            Decimal("3"),
            Decimal("17.50"),
            None,
            {"weekdays": ["fri"], "start_time": "14:00", "end_time": "17:00"},
            {},
            diogo,
            "Plano Rep Gaia",
        ),
        (
            c_rep,
            by_name["Auchan Alfragide"],
            Decimal("4"),
            Decimal("18.00"),
            None,
            {"weekdays": ["tue", "thu"], "start_time": "10:00", "end_time": "14:00"},
            {},
            carla,
            "Plano Rep Alfragide",
        ),
        (
            c_prom,
            by_name["Pingo Doce Chiado"],
            Decimal("2"),
            Decimal("22.00"),
            None,
            {"weekdays": ["fri"], "start_time": "16:00", "end_time": "18:00", "mech": "Degustação"},
            {},
            ana,
            "Plano Prom Chiado",
        ),
        (
            c_prom,
            by_name["Pingo Doce Almada"],
            Decimal("4"),
            Decimal("22.00"),
            None,
            {"weekdays": ["tue"], "start_time": "14:00", "end_time": "18:00", "mech": "Amostra"},
            {},
            None,
            "Plano Prom Almada",
        ),
        (
            c_log,
            by_name["Continente Colombo"],
            None,
            None,
            Decimal("120.00"),
            {"weekdays": ["wed"], "start_time": "08:00", "end_time": "11:00", "svc": "Entrega"},
            {},
            carla,
            "Plano Log Colombo",
        ),
        (
            c_eq,
            by_name["Continente Amadora"],
            None,
            None,
            Decimal("2500.00"),
            {},
            {"base": 2000, "deslocacao": 300, "gestao": 200},
            bruno,
            "Equipa Fixa Amadora",
        ),
    ]

    plans: list[ServicePlan] = []
    for contract, store, hours, rate, fixed, schedule, pricing, emp, plan_name in lines_spec:
        line = ContractLine(
            organization_id=org.id,
            contract_id=contract.id,
            store_id=store.id,
            service_type=contract.type,
            contracted_hours=hours,
            bill_rate=rate,
            fixed_amount=fixed,
            schedule_rules=schedule,
            pricing_components=pricing,
            start_date=contract.start_date,
            end_date=contract.end_date,
            generates_daily_shifts=line_generates_daily_shifts(contract.type),
        )
        db.add(line)
        db.flush()
        if line.generates_daily_shifts:
            plan = ServicePlan(
                organization_id=org.id,
                contract_line_id=line.id,
                name=plan_name,
                recurrence_rule=schedule,
                default_employee_id=emp.id if emp else None,
                active=True,
            )
            db.add(plan)
            db.flush()
            plans.append(plan)

    for contract in (c_rep, c_prom, c_log, c_eq):
        db.refresh(contract)
        db.add(
            ContractVersion(
                organization_id=org.id,
                contract_id=contract.id,
                version=1,
                snapshot={
                    "number": contract.number,
                    "type": contract.type,
                    "billing_model": contract.billing_model,
                    "seed": True,
                },
                reason="Seed inicial",
                author_user_id=admin.id,
            )
        )

    # Absences — Bruno on leave week 45 (approved); pending request for Inês
    db.add(
        Absence(
            organization_id=org.id,
            employee_id=bruno.id,
            absence_type=AbsenceType.FERIAS,
            start_date=week_start,
            end_date=week_start + timedelta(days=6),
            status=AbsenceStatus.APROVADO,
            reason="Férias · 2–8 nov",
            decided_by_user_id=admin.id,
        )
    )
    db.add(
        Absence(
            organization_id=org.id,
            employee_id=ines.id,
            absence_type=AbsenceType.INDISPONIBILIDADE,
            start_date=week_start + timedelta(days=4),
            end_date=week_start + timedelta(days=4),
            status=AbsenceStatus.PEDIDO,
            reason="Consulta médica",
        )
    )

    # Documents — some expiring soon for dashboard alerts (MVP-07)
    db.add_all(
        [
            EmployeeDocument(
                organization_id=org.id,
                employee_id=ana.id,
                doc_type="CARTAO_CIDADAO",
                label="CC Ana",
                expires_on=date(2027, 5, 1),
                status=DocumentStatus.VALIDO,
            ),
            EmployeeDocument(
                organization_id=org.id,
                employee_id=carla.id,
                doc_type="CERTIFICADO_HACCP",
                label="HACCP",
                expires_on=date(2026, 11, 15),
                status=DocumentStatus.VALIDO,
            ),
            EmployeeDocument(
                organization_id=org.id,
                employee_id=diogo.id,
                doc_type="ATESTADO_MEDICO",
                label="Atestado aptidão",
                expires_on=date(2026, 10, 20),
                status=DocumentStatus.EXPIRADO,
            ),
        ]
    )

    db.commit()

    for plan in plans:
        generate_shifts_for_week(
            db,
            organization_id=org.id,
            service_plan=plan,
            week_start=week_start,
            author_user_id=admin.id,
        )

    return org
