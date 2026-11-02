import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Contract, Margin } from "@/api/types";
import { CONTRACT_TYPE_LABEL } from "@/lib/labels";

export function ProfitabilityPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<(Margin & { type?: string })[]>([]);

  useEffect(() => {
    if (!token) return;
    apiFetch<Contract[]>("/contracts", { token }).then(async (contracts) => {
      const margins = await Promise.all(
        contracts.map(async (c) => {
          const m = await apiFetch<Margin>(
            `/contracts/${c.id}/margin?year=2026&month=11`,
            { token },
          );
          return { ...m, type: c.type };
        }),
      );
      setRows(margins);
    });
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Rentabilidade</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Receita prevista vs custos diretos · margem esperada por contrato (MVP-27).
        </p>
      </div>
      <div className="fo-panel overflow-hidden">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Contrato</th>
              <th className="px-4 py-2.5">Tipo</th>
              <th className="px-4 py-2.5">Receita prev.</th>
              <th className="px-4 py-2.5">Custos</th>
              <th className="px-4 py-2.5">Margem</th>
              <th className="px-4 py-2.5">%</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.contract_id} className="border-b border-fo-border last:border-0">
                <td className="px-4 py-3">
                  <div className="font-semibold">{r.contract_number}</div>
                  <div className="text-[12px] text-fo-ink-muted">{r.client_name}</div>
                </td>
                <td className="px-4 py-3">{CONTRACT_TYPE_LABEL[r.type ?? ""] ?? r.type}</td>
                <td className="px-4 py-3 font-mono">{Number(r.expected_revenue).toFixed(2)} €</td>
                <td className="px-4 py-3 font-mono">{Number(r.direct_costs).toFixed(2)} €</td>
                <td className="px-4 py-3 font-mono font-semibold">{Number(r.expected_margin).toFixed(2)} €</td>
                <td className="px-4 py-3 font-mono">{Number(r.margin_pct).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
