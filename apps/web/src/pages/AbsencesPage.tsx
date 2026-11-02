import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Absence, Employee } from "@/api/types";

export function AbsencesPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<Absence[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState("");
  const [absenceType, setAbsenceType] = useState("FERIAS");
  const [startDate, setStartDate] = useState("2026-11-09");
  const [endDate, setEndDate] = useState("2026-11-09");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    const [abs, emps] = await Promise.all([
      apiFetch<Absence[]>("/absences", { token }),
      apiFetch<Employee[]>("/employees", { token }),
    ]);
    setRows(abs);
    setEmployees(emps);
    if (!employeeId && emps[0]) setEmployeeId(emps[0].id);
  }

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Erro"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    try {
      await apiFetch("/absences", {
        method: "POST",
        token,
        body: JSON.stringify({
          employee_id: employeeId,
          absence_type: absenceType,
          start_date: startDate,
          end_date: endDate,
          reason: reason || null,
        }),
      });
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar");
    }
  }

  async function decide(id: string, status: "APROVADO" | "REJEITADO") {
    if (!token) return;
    await apiFetch(`/absences/${id}/decide`, {
      method: "POST",
      token,
      body: JSON.stringify({ status }),
    });
    await load();
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Ausências</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Pedido + aprovação mínima (MVP-15). Equipas fixas usam ausências sem turnos diários (Q06).
        </p>
      </div>

      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}

      <form onSubmit={onCreate} className="fo-panel grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-5">
        <label className="text-[12px] font-semibold text-fo-ink-muted">
          Colaborador
          <select className="fo-field mt-1 w-full" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.full_name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[12px] font-semibold text-fo-ink-muted">
          Tipo
          <select className="fo-field mt-1 w-full" value={absenceType} onChange={(e) => setAbsenceType(e.target.value)}>
            <option value="FERIAS">Férias</option>
            <option value="FALTA">Falta</option>
            <option value="INDISPONIBILIDADE">Indisponibilidade</option>
          </select>
        </label>
        <label className="text-[12px] font-semibold text-fo-ink-muted">
          Início
          <input className="fo-field mt-1 w-full" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </label>
        <label className="text-[12px] font-semibold text-fo-ink-muted">
          Fim
          <input className="fo-field mt-1 w-full" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
        <label className="text-[12px] font-semibold text-fo-ink-muted xl:col-span-1 md:col-span-2">
          Motivo
          <div className="mt-1 flex gap-2">
            <input className="fo-field w-full" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" className="fo-btn-primary shrink-0">
              Pedir
            </button>
          </div>
        </label>
      </form>

      <div className="fo-panel overflow-hidden">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Colaborador</th>
              <th className="px-4 py-2.5">Tipo</th>
              <th className="px-4 py-2.5">Período</th>
              <th className="px-4 py-2.5">Estado</th>
              <th className="px-4 py-2.5">Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id} className="border-b border-fo-border last:border-0">
                <td className="px-4 py-3 font-semibold">{a.employee_name}</td>
                <td className="px-4 py-3">{a.absence_type}</td>
                <td className="px-4 py-3 font-mono text-[12px]">
                  {a.start_date} → {a.end_date}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`fo-badge ${
                      a.status === "APROVADO"
                        ? "bg-fo-success-subtle text-fo-success"
                        : a.status === "REJEITADO"
                          ? "bg-fo-danger-subtle text-fo-danger"
                          : "bg-fo-warning-subtle text-fo-warning"
                    }`}
                  >
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {a.status === "PEDIDO" ? (
                    <div className="flex gap-2">
                      <button type="button" className="fo-btn-primary" onClick={() => void decide(a.id, "APROVADO")}>
                        Aprovar
                      </button>
                      <button type="button" className="fo-btn-secondary" onClick={() => void decide(a.id, "REJEITADO")}>
                        Rejeitar
                      </button>
                    </div>
                  ) : (
                    <span className="text-fo-ink-muted">{a.reason ?? "—"}</span>
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
