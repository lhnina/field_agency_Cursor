import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Budget, Campaign } from "@/api/types";
import { CONTRACT_TYPE_LABEL } from "@/lib/labels";

export function BudgetsPage() {
  const { token } = useAuth();
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!token) return;
    const [b, c] = await Promise.all([
      apiFetch<Budget[]>("/budgets", { token }),
      apiFetch<Campaign[]>("/campaigns", { token }),
    ]);
    setBudgets(b);
    setCampaigns(c);
  }

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : "Erro"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function convert(id: string) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/budgets/${id}/approve-convert`, { method: "POST", token });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha conversão");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Orçamentos & campanhas</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Orçamento aprovado gera Contrato + Campanha (Q02).
        </p>
      </div>
      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Orçamentos</div>
          <ul>
            {budgets.map((b) => (
              <li key={b.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold">
                      {b.number} · {b.title}
                    </div>
                    <div className="text-[12px] text-fo-ink-muted">
                      {b.client_name} · {CONTRACT_TYPE_LABEL[b.contract_type] ?? b.contract_type} ·{" "}
                      {b.status} · {Number(b.total_amount).toFixed(2)} €
                    </div>
                  </div>
                  {b.status !== "CONVERTIDO" && (
                    <button
                      type="button"
                      className="fo-btn-primary"
                      disabled={busy}
                      onClick={() => void convert(b.id)}
                    >
                      Converter
                    </button>
                  )}
                </div>
              </li>
            ))}
            {!budgets.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Sem orçamentos.</li>
            )}
          </ul>
        </div>
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Campanhas</div>
          <ul>
            {campaigns.map((c) => (
              <li key={c.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="font-semibold">{c.name}</div>
                <div className="text-[12px] text-fo-ink-muted">{c.status}</div>
              </li>
            ))}
            {!campaigns.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">
                Converta um orçamento para criar campanha.
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
