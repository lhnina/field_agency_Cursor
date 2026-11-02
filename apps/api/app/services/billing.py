from app.domain.enums import BillingModel, ContractType


def billing_model_for(contract_type: str) -> str:
    """Q10 defaults: hours for reposicao/promocao; fixed for logistica/equipas."""
    if contract_type in {ContractType.REPOSICAO, ContractType.PROMOCAO}:
        return BillingModel.HORAS_CONTRATADAS
    return BillingModel.VALOR_FIXO


def line_generates_daily_shifts(contract_type: str) -> bool:
    """Q06: Equipas Fixas — monthly billing + absences; no daily shifts in MVP."""
    return contract_type != ContractType.EQUIPAS_FIXAS
