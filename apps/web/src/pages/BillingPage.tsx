import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { BillingDraft, BillingPeriod, ErpExportBatch, PayrollStatement } from "@/api/types";
import { CONTRACT_TYPE_LABEL } from "@/lib/labels";

type EngagementFilter = "" | "CT" | "RV";

export function BillingPage() {
  const { token } = useAuth();
  const [periods, setPeriods] = useState<BillingPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [drafts, setDrafts] = useState<BillingDraft[]>([]);
  const [payrollId, setPayrollId] = useState<string>("");
  const [payrollStatus, setPayrollStatus] = useState<string>("ABERTO");
  const [statements, setStatements] = useState<PayrollStatement[]>([]);
  const [engagementFilter, setEngagementFilter] = useState<EngagementFilter>("");
  const [exports, setExports] = useState<ErpExportBatch[]>([]);
  const [reopenReason, setReopenReason] = useState("Correção auditada");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = periods.find((p) => p.id === selectedPeriod);

  const filteredStatements = useMemo(() => {
    if (!engagementFilter) return statements;
    return statements.filter((s) => s.engagement_type === engagementFilter);
  }, [statements, engagementFilter]);

  async function refreshExports() {
    if (!token) return;
    setExports(await apiFetch<ErpExportBatch[]>("/exports", { token }));
  }

  async function loadPeriods() {
    if (!token) return;
    let list = await apiFetch<BillingPeriod[]>("/billing-periods?year=2026&month=11", { token });
    if (!list.length) {
      list = await apiFetch<BillingPeriod[]>("/billing-periods", {
        method: "POST",
        token,
        body: JSON.stringify({ year: 2026, month: 11 }),
      });
    }
    setPeriods(list);
    if (!selectedPeriod && list[0]) setSelectedPeriod(list[0].id);
    const payroll = await apiFetch<{ id: string; status: string }>("/payroll-periods?year=2026&month=11", {
      method: "POST",
      token,
    });
    setPayrollId(payroll.id);
    setPayrollStatus(payroll.status);
    const stmts = await apiFetch<PayrollStatement[]>(`/payroll-periods/${payroll.id}/statements`, {
      token,
    });
    setStatements(stmts);
    await refreshExports();
  }

  useEffect(() => {
    void loadPeriods().catch((err) => setError(err instanceof Error ? err.message : "Erro"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token || !selectedPeriod) return;
    apiFetch<BillingDraft[]>(`/billing-drafts?period_id=${selectedPeriod}`, { token })
      .then(setDrafts)
      .catch(() => setDrafts([]));
  }, [token, selectedPeriod]);

  async function generate() {
    if (!token || !selectedPeriod) return;
    setBusy(true);
    setError(null);
    try {
      const d = await apiFetch<BillingDraft[]>(`/billing-periods/${selectedPeriod}/generate`, {
        method: "POST",
        token,
      });
      setDrafts(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha");
    } finally {
      setBusy(false);
    }
  }

  async function generatePayroll() {
    if (!token || !payrollId) return;
    setBusy(true);
    try {
      const rows = await apiFetch<PayrollStatement[]>(`/payroll-periods/${payrollId}/generate`, {
        method: "POST",
        token,
      });
      setStatements(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha apuramento");
    } finally {
      setBusy(false);
    }
  }

  async function exportBilling() {
    if (!token || !selectedPeriod) return;
    setBusy(true);
    try {
      await apiFetch(`/exports/billing/${selectedPeriod}`, { method: "POST", token });
      await refreshExports();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha export PHC");
    } finally {
      setBusy(false);
    }
  }

  async function exportPayroll(filter: EngagementFilter = engagementFilter) {
    if (!token || !payrollId) return;
    setBusy(true);
    try {
      const q = filter ? `?engagement_type=${filter}` : "";
      await apiFetch(`/exports/payroll/${payrollId}${q}`, { method: "POST", token });
      await refreshExports();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha export remuneração");
    } finally {
      setBusy(false);
    }
  }

  async function closeBillingPeriod() {
    if (!token || !selectedPeriod) return;
    setBusy(true);
    try {
      await apiFetch(`/billing-periods/${selectedPeriod}/close`, { method: "POST", token });
      await loadPeriods();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha fecho");
    } finally {
      setBusy(false);
    }
  }

  async function reopenBillingPeriod() {
    if (!token || !selectedPeriod) return;
    setBusy(true);
    try {
      await apiFetch(`/billing-periods/${selectedPeriod}/reopen`, {
        method: "POST",
        token,
        body: JSON.stringify({ reason: reopenReason }),
      });
      await loadPeriods();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha reabertura");
    } finally {
      setBusy(false);
    }
  }

  async function closePayrollPeriod() {
    if (!token || !payrollId) return;
    setBusy(true);
    try {
      await apiFetch(`/payroll-periods/${payrollId}/close`, { method: "POST", token });
      await loadPeriods();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha fecho apuramento");
    } finally {
      setBusy(false);
    }
  }

  async function batchAction(id: string, action: "ack" | "error" | "retry" | "mark-sent") {
    if (!token) return;
    setBusy(true);
    try {
      const body =
        action === "ack"
          ? JSON.stringify({ ack_reference: `PHC-${Date.now()}` })
          : action === "error"
            ? JSON.stringify({ error_message: "Erro PHC simulado" })
            : undefined;
      await apiFetch(`/exports/${id}/${action}`, {
        method: "POST",
        token,
        body,
      });
      await refreshExports();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha batch");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Pré-faturação & PHC</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Fecho de período · mapa RV · ACK/ERROR/retry · export filtrado
        </p>
      </div>

      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select
          className="fo-field"
          value={selectedPeriod}
          onChange={(e) => setSelectedPeriod(e.target.value)}
        >
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.year}-{String(p.month).padStart(2, "0")} ·{" "}
              {CONTRACT_TYPE_LABEL[p.service_area] ?? p.service_area} · {p.status}
            </option>
          ))}
        </select>
        <button type="button" className="fo-btn-primary" disabled={busy} onClick={() => void generate()}>
          Gerar pré-fatura
        </button>
        <button type="button" className="fo-btn-secondary" disabled={busy} onClick={() => void exportBilling()}>
          Export PHC faturação
        </button>
        {selected?.status !== "FECHADO" ? (
          <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void closeBillingPeriod()}>
            Fechar período faturação
          </button>
        ) : (
          <>
            <input
              className="fo-field max-w-[12rem]"
              value={reopenReason}
              onChange={(e) => setReopenReason(e.target.value)}
              placeholder="Motivo reabertura"
            />
            <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void reopenBillingPeriod()}>
              Reabrir (auditado)
            </button>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="fo-btn-secondary" disabled={busy} onClick={() => void generatePayroll()}>
          Gerar apuramento
        </button>
        <select
          className="fo-field"
          value={engagementFilter}
          onChange={(e) => setEngagementFilter(e.target.value as EngagementFilter)}
        >
          <option value="">Todos (CT+RV)</option>
          <option value="RV">Só RV</option>
          <option value="CT">Só CT</option>
        </select>
        <button type="button" className="fo-btn-accent" disabled={busy} onClick={() => void exportPayroll()}>
          Export remuneração{engagementFilter ? ` · ${engagementFilter}` : ""}
        </button>
        {payrollStatus !== "FECHADO" ? (
          <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void closePayrollPeriod()}>
            Fechar apuramento ({payrollStatus})
          </button>
        ) : (
          <span className="text-[12px] text-fo-ink-muted">Apuramento FECHADO</span>
        )}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Pré-faturas</div>
          <ul>
            {drafts.map((d) => (
              <li key={d.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="flex justify-between gap-2">
                  <div>
                    <div className="font-semibold">{d.client_name}</div>
                    <div className="text-[12px] text-fo-ink-muted">
                      {d.lines.length} linhas · IVA {d.vat_rate}% · {d.cost_center}
                    </div>
                  </div>
                  <div className="text-right font-mono text-[13px]">
                    <div>{Number(d.total_net).toFixed(2)} €</div>
                    <div className="text-fo-ink-muted">{Number(d.total_gross).toFixed(2)} € c/ IVA</div>
                  </div>
                </div>
              </li>
            ))}
            {!drafts.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Sem drafts — gerar pré-fatura.</li>
            )}
          </ul>
        </div>

        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">
            Mapa apuramento {engagementFilter === "RV" ? "· RV" : engagementFilter === "CT" ? "· CT" : ""}
          </div>
          <table className="w-full text-left text-[13px]">
            <thead className="bg-fo-surface-raised text-[11px] font-bold uppercase text-fo-ink-muted">
              <tr>
                <th className="px-3 py-2">Cliente</th>
                <th className="px-3 py-2">Horas</th>
                <th className="px-3 py-2">Valor</th>
                <th className="px-3 py-2">Vínculo</th>
              </tr>
            </thead>
            <tbody>
              {filteredStatements.map((s) => (
                <tr key={s.id} className="border-t border-fo-border">
                  <td className="px-3 py-2">
                    <div className="font-semibold">{s.client_name}</div>
                    <div className="text-[12px] text-fo-ink-muted">{s.employee_name}</div>
                  </td>
                  <td className="px-3 py-2 font-mono">{Number(s.hours).toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono">{Number(s.amount).toFixed(2)} €</td>
                  <td className="px-3 py-2">{s.engagement_type}</td>
                </tr>
              ))}
              {!filteredStatements.length && (
                <tr>
                  <td colSpan={4} className="px-3 py-3 text-fo-ink-muted">
                    Sem linhas para o filtro.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="fo-panel overflow-hidden">
        <div className="border-b border-fo-border px-4 py-3 font-bold">Batches export PHC</div>
        <ul>
          {exports.map((b) => (
            <li key={b.id} className="border-b border-fo-border px-4 py-3 last:border-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold">
                    {b.filename} · {b.batch_type} · {b.status}
                    {b.retry_count ? ` · retry ${b.retry_count}` : ""}
                  </div>
                  {b.ack_reference && (
                    <div className="text-[12px] text-fo-ink-muted">ACK {b.ack_reference}</div>
                  )}
                  {b.error_message && (
                    <div className="text-[12px] text-fo-danger">{b.error_message}</div>
                  )}
                  <pre className="mt-1 max-h-24 overflow-auto rounded-fo bg-fo-surface-raised p-2 font-mono text-[11px]">
                    {b.content_preview}
                  </pre>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void batchAction(b.id, "mark-sent")}>
                    Sent
                  </button>
                  <button type="button" className="fo-btn-secondary" disabled={busy} onClick={() => void batchAction(b.id, "ack")}>
                    ACK
                  </button>
                  <button type="button" className="fo-btn-ghost" disabled={busy} onClick={() => void batchAction(b.id, "error")}>
                    ERROR
                  </button>
                  <button type="button" className="fo-btn-accent" disabled={busy} onClick={() => void batchAction(b.id, "retry")}>
                    Retry
                  </button>
                  <a
                    className="fo-btn-secondary"
                    href={`/api/v1/exports/${b.id}/download`}
                    onClick={async (e) => {
                      e.preventDefault();
                      if (!token) return;
                      const res = await fetch(`/api/v1/exports/${b.id}/download`, {
                        headers: { Authorization: `Bearer ${token}` },
                      });
                      const blob = await res.blob();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = b.filename;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    Download CSV
                  </a>
                </div>
              </div>
            </li>
          ))}
          {!exports.length && (
            <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Ainda sem exports.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
