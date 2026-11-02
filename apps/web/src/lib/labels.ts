export const CONTRACT_TYPE_LABEL: Record<string, string> = {
  REPOSICAO: "Reposição",
  PROMOCAO: "Promoção",
  LOGISTICA: "Logística",
  EQUIPAS_FIXAS: "Equipas fixas",
};

export const HOUR_LABELS = [
  { key: "hours_contracted", label: "Contratadas" },
  { key: "hours_planned", label: "Planeadas" },
  { key: "hours_assigned", label: "Afetadas" },
  { key: "hours_executed", label: "Executadas" },
  { key: "hours_approved", label: "Aprovadas" },
  { key: "hours_billable", label: "Faturáveis" },
  { key: "hours_payable", label: "Remuneráveis" },
] as const;

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

export function slotClass(type: string, unassigned: boolean): string {
  if (unassigned) return "fo-slot-empty";
  switch (type) {
    case "REPOSICAO":
      return "fo-slot-rep";
    case "PROMOCAO":
      return "fo-slot-prom";
    case "LOGISTICA":
      return "fo-slot-log";
    case "EQUIPAS_FIXAS":
      return "fo-slot-eq";
    default:
      return "fo-slot-rep";
  }
}

export function shortType(type: string): string {
  switch (type) {
    case "REPOSICAO":
      return "Rep";
    case "PROMOCAO":
      return "Prom";
    case "LOGISTICA":
      return "Log";
    case "EQUIPAS_FIXAS":
      return "Eq";
    default:
      return type;
  }
}
