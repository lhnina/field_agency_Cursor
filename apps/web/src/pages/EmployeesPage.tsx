import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Employee } from "@/api/types";
import { initials } from "@/lib/labels";

export function EmployeesPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<Employee[]>([]);

  useEffect(() => {
    if (!token) return;
    apiFetch<Employee[]>("/employees", { token }).then(setRows);
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Colaboradores</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">Ficha mínima · vínculo, zona e custos.</p>
      </div>
      <div className="fo-panel overflow-hidden">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Nome</th>
              <th className="px-4 py-2.5">Vínculo</th>
              <th className="px-4 py-2.5">Zona</th>
              <th className="px-4 py-2.5">Custo/h</th>
              <th className="px-4 py-2.5">Estado</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-b border-fo-border last:border-0">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="grid h-8 w-8 place-items-center rounded-fo bg-fo-brand-subtle text-[12px] font-bold text-fo-brand">
                      {initials(e.full_name)}
                    </div>
                    <div>
                      <div className="font-semibold">{e.full_name}</div>
                      <div className="text-[12px] text-fo-ink-muted">{e.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">{e.engagement_type}</td>
                <td className="px-4 py-3">{e.zone_code}</td>
                <td className="px-4 py-3 font-mono">{e.hourly_cost ? `${e.hourly_cost} €` : "—"}</td>
                <td className="px-4 py-3">
                  <span className="fo-badge bg-fo-success-subtle text-fo-success">{e.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
