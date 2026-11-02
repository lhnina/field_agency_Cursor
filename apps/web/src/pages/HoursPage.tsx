import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { TimeEntry } from "@/api/types";
import { HOUR_LABELS } from "@/lib/labels";

export function HoursPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<TimeEntry[]>([]);
  const [filter, setFilter] = useState<string>("SUBMETIDO");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!token) return;
    const q = filter ? `?status=${filter}` : "";
    setRows(await apiFetch<TimeEntry[]>(`/time-entries${q}`, { token }));
  }

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Erro"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filter]);

  async function act(id: string, action: string, allowExtra = false) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/time-entries/${id}/validate`, {
        method: "POST",
        token,
        body: JSON.stringify({
          action,
          allow_extra_billable: allowExtra,
          adjustment_note: action === "REJEITAR" ? "Rejeitado no back-office" : "Validação supervisor",
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha");
    } finally {
      setBusy(false);
    }
  }

  async function autoApprove() {
    if (!token) return;
    setBusy(true);
    try {
      await apiFetch("/time-entries/auto-approve?as_of=2026-12-31", { method: "POST", token });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha auto-aprovação");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">Validação de horas</h1>
          <p className="text-[13.5px] text-fo-ink-secondary">
            Aprovar / rejeitar / ajustar · teto contratado (Q11) · auto após 3 dias úteis (Q12)
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="fo-field" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="SUBMETIDO">Pendentes</option>
            <option value="APROVADO">Aprovados</option>
            <option value="REJEITADO">Rejeitados</option>
            <option value="">Todos</option>
          </select>
          <button type="button" className="fo-btn-secondary" disabled={busy} onClick={() => void autoApprove()}>
            Correr auto-aprovação Q12
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}

      <div className="fo-panel overflow-auto">
        <table className="w-full min-w-[900px] text-left text-[13px]">
          <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
            <tr>
              <th className="px-3 py-2.5">Loja / tipo</th>
              <th className="px-3 py-2.5">Estado</th>
              {HOUR_LABELS.map((h) => (
                <th key={h.key} className="px-2 py-2.5">
                  {h.label.slice(0, 4)}
                </th>
              ))}
              <th className="px-3 py-2.5">Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-b border-fo-border last:border-0">
                <td className="px-3 py-3">
                  <div className="font-semibold">{e.store_name ?? "—"}</div>
                  <div className="text-[12px] text-fo-ink-muted">
                    {e.shift_type}
                    {e.auto_approved ? " · auto" : ""}
                    {e.tacit_accepted ? " · tácito" : ""}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <span className="fo-badge bg-fo-surface-raised text-fo-ink-secondary">{e.status}</span>
                </td>
                {HOUR_LABELS.map((h) => (
                  <td key={h.key} className="px-2 py-3 font-mono text-[12px]">
                    {Number(e[h.key]).toFixed(1)}
                  </td>
                ))}
                <td className="px-3 py-3">
                  {e.status === "SUBMETIDO" ? (
                    <div className="flex flex-wrap gap-1.5">
                      <button type="button" className="fo-btn-primary" disabled={busy} onClick={() => void act(e.id, "APROVAR")}>
                        Aprovar
                      </button>
                      <button
                        type="button"
                        className="fo-btn-secondary"
                        disabled={busy}
                        onClick={() => void act(e.id, "AJUSTAR", true)}
                        title="Permite faturar acima do contratado (Q11)"
                      >
                        Extra
                      </button>
                      <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void act(e.id, "REJEITAR")}>
                        Rejeitar
                      </button>
                    </div>
                  ) : (
                    <span className="text-[12px] text-fo-ink-muted">{e.adjustment_note ?? "—"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
