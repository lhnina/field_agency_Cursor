import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { AlertItem, Contract, Employee, PlanningWeek } from "@/api/types";

export function DashboardPage() {
  const { token, user } = useAuth();
  const [stats, setStats] = useState({ contracts: 0, employees: 0, shifts: 0, unassigned: 0 });
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetch<Contract[]>("/contracts", { token }),
      apiFetch<Employee[]>("/employees", { token }),
      apiFetch<PlanningWeek>("/planning/week?week_start=2026-11-02", { token }),
      apiFetch<AlertItem[]>("/alerts?week_start=2026-11-02", { token }),
    ]).then(([contracts, employees, week, alertList]) => {
      setStats({
        contracts: contracts.length,
        employees: employees.length,
        shifts: week.shifts.length,
        unassigned: week.unassigned_count ?? week.shifts.filter((s) => s.assignments.length === 0).length,
      });
      setAlerts(alertList);
    });
  }, [token]);

  const kpis = [
    { label: "Contratos ativos", value: String(stats.contracts) },
    { label: "Colaboradores", value: String(stats.employees) },
    { label: "Turnos (sem. 45)", value: String(stats.shifts) },
    { label: "Sem recurso", value: String(stats.unassigned), warn: true },
  ];

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
          Olá, {user?.full_name.split(" ")[0]} — resumo da semana demo (2–8 nov 2026).
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
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
          <span className="text-[12px] text-fo-ink-muted">
            Docs · sem recurso · CT informativo (Q20)
          </span>
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
            Abrir planeamento
          </Link>
          <Link to="/ausencias" className="fo-btn-secondary">
            Ausências
          </Link>
          <Link to="/contratos" className="fo-btn-secondary">
            Ver contratos
          </Link>
          <Link to="/colaboradores" className="fo-btn-secondary">
            Colaboradores
          </Link>
        </div>
      </div>
    </div>
  );
}
