import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { AlertItem, DashboardKpis } from "@/api/types";

export function DashboardPage() {
  const { token, user } = useAuth();
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetch<DashboardKpis>("/dashboard/kpis?week_start=2026-11-02&year=2026&month=11", { token }),
      apiFetch<AlertItem[]>("/alerts?week_start=2026-11-02", { token }),
    ]).then(([k, a]) => {
      setKpis(k);
      setAlerts(a);
    });
  }, [token]);

  const cards = kpis
    ? [
        { label: "Contratos", value: String(kpis.contracts) },
        { label: "Colaboradores", value: String(kpis.employees) },
        { label: "Turnos (sem.)", value: String(kpis.shifts_week) },
        { label: "Sem recurso", value: String(kpis.unassigned_week), warn: true },
        { label: "Pend. validação", value: String(kpis.pending_validation), warn: true },
        { label: "Horas aprovadas", value: Number(kpis.approved_hours_month).toFixed(1) },
        { label: "Margem prev. €", value: Number(kpis.expected_margin_total).toFixed(0) },
        { label: "Exports PHC", value: String(kpis.export_batches) },
      ]
    : [];

  const severityClass: Record<string, string> = {
    danger: "border-fo-danger/30 bg-fo-danger-subtle text-fo-danger",
    warning: "border-fo-warning/30 bg-fo-warning-subtle text-fo-warning",
    info: "border-fo-info/30 bg-fo-info-subtle text-fo-info",
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Dashboard operacional</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Olá, {user?.full_name.split(" ")[0]} — KPIs semana 45 + fecho nov/2026.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((kpi) => (
          <div key={kpi.label} className="fo-panel px-4 py-3">
            <div className="text-[12px] font-semibold text-fo-ink-muted">{kpi.label}</div>
            <div
              className={`mt-1 font-mono text-[28px] font-semibold tracking-tight ${
                kpi.warn ? "text-fo-accent-hover" : "text-fo-ink"
              }`}
            >
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      <div className="fo-panel p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-bold">Alertas</h2>
          <span className="text-[12px] text-fo-ink-muted">Docs · sem recurso · CT (Q20)</span>
        </div>
        <ul className="mt-3 space-y-2">
          {alerts.length === 0 && (
            <li className="text-[13px] text-fo-ink-muted">Sem alertas para a semana.</li>
          )}
          {alerts.slice(0, 8).map((a) => (
            <li
              key={`${a.kind}-${a.entity_id}-${a.message}`}
              className={`rounded-fo border px-3 py-2 text-[13px] ${severityClass[a.severity] ?? severityClass.info}`}
            >
              <div className="font-semibold">{a.title}</div>
              <div>{a.message}</div>
            </li>
          ))}
        </ul>
      </div>

      <div className="fo-panel p-4">
        <h2 className="text-base font-bold">Atalhos</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link to="/planeamento" className="fo-btn-primary">
            Planeamento
          </Link>
          <Link to="/horas" className="fo-btn-secondary">
            Validar horas
          </Link>
          <Link to="/faturacao" className="fo-btn-secondary">
            Pré-faturação / PHC
          </Link>
          <Link to="/rentabilidade" className="fo-btn-secondary">
            Rentabilidade
          </Link>
        </div>
      </div>
    </div>
  );
}
