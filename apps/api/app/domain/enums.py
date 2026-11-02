"""Domain enumerations — FieldOps MVP.

Hour concepts (7 horas) are first-class even when UI is partial.
CT compliance = alerts only (Q20).
"""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMINISTRADOR = "ADMINISTRADOR"
    DIRECAO = "DIRECAO"
    GESTOR_OPERACIONAL = "GESTOR_OPERACIONAL"
    SUPERVISOR = "SUPERVISOR"
    RH = "RH"
    FINANCEIRO = "FINANCEIRO"
    COLABORADOR = "COLABORADOR"


class ContractType(StrEnum):
    REPOSICAO = "REPOSICAO"
    PROMOCAO = "PROMOCAO"
    LOGISTICA = "LOGISTICA"
    EQUIPAS_FIXAS = "EQUIPAS_FIXAS"


class ContractStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    ATIVO = "ATIVO"
    SUSPENSO = "SUSPENSO"
    ENCERRADO = "ENCERRADO"


class BillingModel(StrEnum):
    """Q10 defaults per contract type."""

    HORAS_CONTRATADAS = "HORAS_CONTRATADAS"  # reposição, promoção
    VALOR_FIXO = "VALOR_FIXO"  # logística, equipas fixas


class EngagementType(StrEnum):
    CONTRATO_TRABALHO = "CT"
    RECIBOS_VERDES = "RV"


class ShiftStatus(StrEnum):
    PLANEADO = "PLANEADO"
    ATRIBUIDO = "ATRIBUIDO"
    CONFIRMADO = "CONFIRMADO"
    EM_EXECUCAO = "EM_EXECUCAO"
    CONCLUIDO = "CONCLUIDO"
    PENDENTE_VALIDACAO = "PENDENTE_VALIDACAO"
    VALIDADO = "VALIDADO"
    REJEITADO = "REJEITADO"
    CANCELADO = "CANCELADO"


class HourConcept(StrEnum):
    """Seven trackable hour states (§4.4)."""

    CONTRATADAS = "CONTRATADAS"
    PLANEADAS = "PLANEADAS"
    AFETADAS = "AFETADAS"
    EXECUTADAS = "EXECUTADAS"
    APROVADAS = "APROVADAS"
    FATURAVEIS = "FATURAVEIS"
    REMUNERAVEIS = "REMUNERAVEIS"


class TimeEntryStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    SUBMETIDO = "SUBMETIDO"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class AbsenceType(StrEnum):
    FERIAS = "FERIAS"
    FALTA = "FALTA"
    INDISPONIBILIDADE = "INDISPONIBILIDADE"


class AbsenceStatus(StrEnum):
    PEDIDO = "PEDIDO"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class DocumentStatus(StrEnum):
    VALIDO = "VALIDO"
    EXPIRADO = "EXPIRADO"
    PENDENTE = "PENDENTE"


class AlertKind(StrEnum):
    UNASSIGNED_SHIFT = "UNASSIGNED_SHIFT"
    DOC_EXPIRING = "DOC_EXPIRING"
    DOC_EXPIRED = "DOC_EXPIRED"
    OVERLAP = "OVERLAP"
    CT_HOURS = "CT_HOURS"  # alerts only (Q20)
