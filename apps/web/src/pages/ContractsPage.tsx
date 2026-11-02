import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Contract } from "@/api/types";
import { CONTRACT_TYPE_LABEL } from "@/lib/labels";

export function ContractsPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<Contract[]>([]);
  const [selected, setSelected] = useState<Contract | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<Contract[]>("/contracts", { token }).then((data) => {
      setRows(data);
      setSelected(data[0] ?? null);
    });
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Contratos</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Tipados · linhas multi-loja · versionamento stub.
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_380px]">
        <div className="fo-panel overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
              <tr>
                <th className="px-4 py-2.5">Número</th>
                <th className="px-4 py-2.5">Tipo</th>
                <th className="px-4 py-2.5">Faturação</th>
                <th className="px-4 py-2.5">Versão</th>
                <th className="px-4 py-2.5">Linhas</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.id}
                  className={`cursor-pointer border-b border-fo-border last:border-0 hover:bg-fo-surface-raised ${
                    selected?.id === c.id ? "bg-fo-brand-subtle/50" : ""
                  }`}
                  onClick={() => setSelected(c)}
                >
                  <td className="px-4 py-3 font-semibold">{c.number}</td>
                  <td className="px-4 py-3">{CONTRACT_TYPE_LABEL[c.type] ?? c.type}</td>
                  <td className="px-4 py-3 font-mono text-[12px]">{c.billing_model}</td>
                  <td className="px-4 py-3 font-mono">v{c.version}</td>
                  <td className="px-4 py-3">{c.lines.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <aside className="fo-panel p-4">
          {selected ? (
            <div className="space-y-3">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-fo-ink-muted">
                  Detalhe
                </div>
                <h2 className="text-base font-bold">{selected.number}</h2>
                <p className="text-[13px] text-fo-ink-secondary">
                  {CONTRACT_TYPE_LABEL[selected.type]} · {selected.status}
                </p>
              </div>
              {selected.type === "EQUIPAS_FIXAS" && (
                <div className="rounded-fo bg-fo-warning-subtle px-3 py-2 text-[13px] text-fo-warning">
                  Equipas fixas: faturação mensal + ausências; sem turnos diários no MVP.
                </div>
              )}
              <div className="space-y-2">
                {selected.lines.map((line) => (
                  <div key={line.id} className="rounded-fo border border-fo-border px-3 py-2 text-[13px]">
                    <div className="font-semibold">{line.service_type}</div>
                    <div className="text-fo-ink-muted">
                      Loja {line.store_id.slice(0, 8)}… ·{" "}
                      {line.contracted_hours
                        ? `${line.contracted_hours}h · ${line.bill_rate ?? "—"} €/h`
                        : `fixo ${line.fixed_amount ?? "—"} €`}
                    </div>
                    <div className="text-[12px] text-fo-ink-muted">
                      Turnos diários: {line.generates_daily_shifts ? "sim" : "não"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-fo-ink-muted">Selecione um contrato.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
