from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.domain.enums import ContractType, HourConcept, RoleCode, ShiftStatus
from app.models import Role, User
from app.schemas.common import RoleOut

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/roles", response_model=list[RoleOut])
def list_roles(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)))


@router.get("/enums")
def enums(_: User = Depends(get_current_user)) -> dict:
    return {
        "roles": [r.value for r in RoleCode],
        "contract_types": [c.value for c in ContractType],
        "shift_statuses": [s.value for s in ShiftStatus],
        "hour_concepts": [h.value for h in HourConcept],
        "notes": {
            "ct": "Alertas apenas no MVP (Q20)",
            "equipas_fixas": "Faturação mensal + ausências; sem turnos diários (Q06)",
            "assignment": "Afetação estável ao nível do planeamento (Q04)",
            "platform": "Plataforma é master operacional; export PHC mais tarde (Q01)",
        },
    }
