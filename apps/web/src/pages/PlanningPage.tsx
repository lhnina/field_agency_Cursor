import { useEffect, useMemo, useState } from "react";
import { addDays, format, parseISO, startOfWeek } from "date-fns";
import { pt } from "date-fns/locale";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Absence, PlanningWeek, Shift, Substitution, TimeEntry } from "@/api/types";
import { CONTRACT_TYPE_LABEL, HOUR_LABELS, initials, shortType, slotClass } from "@/lib/labels";

const WEEK_ANCHOR = "2026-11-02";

function fmtHour(iso: string) {
  return format(parseISO(iso), "HH:mm");
}

function coversDay(absence: Absence, day: Date) {
  const d = format(day, "yyyy-MM-dd");
  return absence.start_date <= d && absence.end_date >= d && absence.status === "APROVADO";
}

export function PlanningPage() {
  const { token } = useAuth();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(parseISO(WEEK_ANCHOR), { weekStartsOn: 1 }));
  const [data, setData] = useState<PlanningWeek | null>(null);
  const [selected, setSelected] = useState<Shift | null>(null);
  const [timeEntry, setTimeEntry] = useState<TimeEntry | null>(null);
  const [history, setHistory] = useState<Substitution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyGen, setBusyGen] = useState(false);
  const [assignId, setAssignId] = useState("");
  const [stableDefault, setStableDefault] = useState(true);
  const [substId, setSubstId] = useState("");
  const [substReason, setSubstReason] = useState("Substituição operacional");
  const [showSubstModal, setShowSubstModal] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);

  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  async function load() {
    if (!token) return;
    setError(null);
    try {
      const ws = format(weekStart, "yyyy-MM-dd");
      const week = await apiFetch<PlanningWeek>(`/planning/week?week_start=${ws}`, { token });
      setData(week);
      setSelected((prev) => (prev ? week.shifts.find((s) => s.id === prev.id) ?? null : null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar planeamento");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, weekStart]);

  useEffect(() => {
    if (!token || !selected) {
      setTimeEntry(null);
      setHistory([]);
      return;
    }
    apiFetch<TimeEntry>(`/shifts/${selected.id}/time-entry`, { token })
      .then(setTimeEntry)
      .catch(() => setTimeEntry(null));
    apiFetch<Substitution[]>(`/substitutions?shift_id=${selected.id}`, { token })
      .then(setHistory)
      .catch(() => setHistory([]));
    const current = selected.assignments[0]?.employee_id ?? "";
    setAssignId(current);
    setSubstId("");
  }, [token, selected]);

  async function generateAll() {
    if (!token) return;
    setBusyGen(true);
    try {
      const plans = await apiFetch<{ id: string }[]>("/service-plans", { token });
      const ws = format(weekStart, "yyyy-MM-dd");
      for (const plan of plans) {
        await apiFetch("/shifts/generate", {
          method: "POST",
          token,
          body: JSON.stringify({ service_plan_id: plan.id, week_start: ws }),
        });
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na geração");
    } finally {
      setBusyGen(false);
    }
  }

  async function assignSelected() {
    if (!token || !selected || !assignId) return;
    setBusyAction(true);
    setError(null);
    try {
      const updated = await apiFetch<Shift>(`/shifts/${selected.id}/assign`, {
        method: "POST",
        token,
        body: JSON.stringify({
          employee_id: assignId,
          set_as_stable_default: stableDefault,
        }),
      });
      setSelected(updated);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na afetação");
    } finally {
      setBusyAction(false);
    }
  }

  async function substituteSelected() {
    if (!token || !selected || !substId) return;
    setBusyAction(true);
    setError(null);
    try {
      await apiFetch<Substitution>(`/shifts/${selected.id}/substitute`, {
        method: "POST",
        token,
        body: JSON.stringify({
          substitute_employee_id: substId,
          reason: substReason,
        }),
      });
      setShowSubstModal(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na substituição");
    } finally {
      setBusyAction(false);
    }
  }

  const rows = useMemo(() => {
    if (!data) return [];
    const absences = data.absences ?? [];
    const byEmployee = new Map<
      string,
      { name: string; meta: string; shifts: Shift[]; absence?: Absence }
    >();
    for (const emp of data.employees) {
      const absence = absences.find((a) => a.employee_id === emp.id && a.status === "APROVADO");
      byEmployee.set(emp.id, {
        name: emp.full_name,
        meta: `${emp.zone_code} · ${emp.engagement_type}`,
        shifts: [],
        absence,
      });
    }
    const unassigned: Shift[] = [];
    for (const shift of data.shifts) {
      if (onlyUnassigned && shift.assignments.length > 0) continue;
      const asg = shift.assignments[0];
      if (!asg) {
        unassigned.push(shift);
        continue;
      }
      const row = byEmployee.get(asg.employee_id);
      if (row) row.shifts.push(shift);
      else unassigned.push(shift);
    }
    const result = [...byEmployee.entries()].map(([id, row]) => ({ id, ...row }));
    result.push({
      id: "__unassigned",
      name: "Por atribuir",
      meta: `${data.unassigned_count ?? unassigned.length} slots`,
      shifts: unassigned,
    });
    return result;
  }, [data, onlyUnassigned]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">Planeamento de serviços</h1>
          <p className="text-[13.5px] text-fo-ink-secondary">
            Vista por colaboradores · {format(weekStart, "d MMM", { locale: pt })} –{" "}
            {format(addDays(weekStart, 6), "d MMM yyyy", { locale: pt })}
            {data?.unassigned_count ? ` · ${data.unassigned_count} sem recurso` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="fo-btn-secondary" onClick={() => setWeekStart((d) => addDays(d, -7))}>
            ‹ Semana anterior
          </button>
          <button type="button" className="fo-btn-secondary" onClick={() => setWeekStart((d) => addDays(d, 7))}>
            Semana seguinte ›
          </button>
          <button type="button" className="fo-btn-secondary" onClick={() => void generateAll()} disabled={busyGen}>
            {busyGen ? "A gerar…" : "Gerar recorrência"}
          </button>
          <button
            type="button"
            className="fo-btn-accent"
            onClick={() => setShowSubstModal(true)}
            disabled={!selected || !selected.assignments.length}
          >
            Substituição rápida
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="fo-field">
          <span className="text-fo-ink-muted">Vista</span>
          <select className="border-0 bg-transparent outline-none">
            <option>Colaboradores</option>
          </select>
        </div>
        <label className="fo-field cursor-pointer gap-2">
          <input
            type="checkbox"
            checked={onlyUnassigned}
            onChange={(e) => setOnlyUnassigned(e.target.checked)}
          />
          Só sem recurso
        </label>
        <span className="fo-badge bg-fo-brand-subtle text-fo-brand">Reposição</span>
        <span className="fo-badge bg-fo-info-subtle text-fo-info">Promoção</span>
        <span className="fo-badge bg-[#efeaf8] text-fo-logistica">Logística</span>
        <span className="fo-badge bg-fo-accent-subtle text-fo-accent-hover">Por atribuir</span>
      </div>

      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}

      <div className="grid gap-3 xl:grid-cols-[1fr_340px]">
        <div className="fo-panel overflow-auto">
          <table className="w-full min-w-[900px] border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-fo-border bg-fo-surface-raised">
                <th className="sticky left-0 bg-fo-surface-raised px-3 py-2.5 text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
                  Colaborador
                </th>
                {days.map((day) => (
                  <th
                    key={day.toISOString()}
                    className="px-2 py-2.5 text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted"
                  >
                    {format(day, "EEE dd", { locale: pt })}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const blocked = row.absence && days.every((d) => coversDay(row.absence!, d));
                return (
                  <tr key={row.id} className="border-b border-fo-border align-top">
                    <td className="sticky left-0 bg-fo-surface px-3 py-3">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`grid h-8 w-8 place-items-center rounded-fo text-[12px] font-bold ${
                            row.id === "__unassigned"
                              ? "bg-fo-accent-subtle text-fo-accent-hover"
                              : "bg-fo-brand-subtle text-fo-brand"
                          }`}
                        >
                          {row.id === "__unassigned" ? "?" : initials(row.name)}
                        </div>
                        <div>
                          <div className="font-semibold">{row.name}</div>
                          <div className="text-[12px] text-fo-ink-muted">{row.meta}</div>
                        </div>
                      </div>
                    </td>
                    {blocked ? (
                      <td colSpan={7} className="px-2 py-2">
                        <div className="rounded-fo-sm border border-fo-border bg-fo-surface-raised px-3 py-2 text-[12px] text-fo-ink-secondary">
                          {row.absence?.absence_type} · {row.absence?.start_date}–{row.absence?.end_date}{" "}
                          (bloqueado) — {row.absence?.reason ?? "ausência aprovada"}
                        </div>
                      </td>
                    ) : (
                      days.map((day) => {
                        const key = format(day, "yyyy-MM-dd");
                        const dayAbsence = row.absence && coversDay(row.absence, day);
                        const dayShifts = row.shifts.filter(
                          (s) => format(parseISO(s.planned_start), "yyyy-MM-dd") === key,
                        );
                        return (
                          <td key={key} className="px-1.5 py-2">
                            {dayAbsence && (
                              <div className="mb-1 rounded-fo-sm bg-fo-warning-subtle px-2 py-1 text-[11px] text-fo-warning">
                                Ausência
                              </div>
                            )}
                            <div className="flex flex-col gap-1.5">
                              {dayShifts.map((shift) => {
                                const unassigned = shift.assignments.length === 0;
                                const storeShort = (shift.store_name ?? "").split(" ").slice(-1)[0] ?? "";
                                return (
                                  <button
                                    key={shift.id}
                                    type="button"
                                    draggable
                                    onDragStart={(e) => {
                                      e.dataTransfer.setData("text/shift-id", shift.id);
                                    }}
                                    onDragOver={(e) => e.preventDefault()}
                                    onDrop={(e) => {
                                      e.preventDefault();
                                      const sid = e.dataTransfer.getData("text/shift-id");
                                      if (sid) {
                                        const found = data?.shifts.find((s) => s.id === sid);
                                        if (found) setSelected(found);
                                      }
                                    }}
                                    className={`${slotClass(shift.shift_type, unassigned)} text-left ${
                                      selected?.id === shift.id ? "ring-2 ring-fo-brand" : ""
                                    }`}
                                    onClick={() => setSelected(shift)}
                                  >
                                    {shortType(shift.shift_type)} · {storeShort}
                                    <br />
                                    {fmtHour(shift.planned_start)}–{fmtHour(shift.planned_end)}
                                    {unassigned ? " · s/ recurso" : ""}
                                    {shift.assignments[0]?.is_substitute ? " · subst." : ""}
                                  </button>
                                );
                              })}
                            </div>
                          </td>
                        );
                      })
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <aside className="fo-panel flex flex-col">
          <div className="border-b border-fo-border px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-fo-ink-muted">
              Detalhe do turno
            </div>
            <h2 className="mt-1 text-base font-bold">
              {selected ? selected.store_name ?? "Turno" : "Selecione um slot"}
            </h2>
            {selected && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="fo-badge bg-fo-brand-subtle text-fo-brand">
                  {CONTRACT_TYPE_LABEL[selected.shift_type] ?? selected.shift_type}
                </span>
                <span className="fo-badge bg-fo-surface-raised text-fo-ink-secondary">{selected.status}</span>
              </div>
            )}
          </div>
          <div className="flex-1 space-y-3 px-4 py-3 text-[13.5px]">
            {!selected && (
              <p className="text-fo-ink-muted">
                Clique num serviço para afetar (Q30), substituir ou ver as 7 horas. Afetação estável grava no
                plano (Q04).
              </p>
            )}
            {selected && (
              <>
                <div>
                  <div className="text-[12px] font-semibold text-fo-ink-muted">Horário</div>
                  <div className="font-mono text-[13px]">
                    {fmtHour(selected.planned_start)} – {fmtHour(selected.planned_end)}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[12px] font-semibold text-fo-ink-muted">Afetar colaborador</div>
                  <select
                    className="fo-field w-full"
                    value={assignId}
                    onChange={(e) => setAssignId(e.target.value)}
                  >
                    <option value="">— selecionar —</option>
                    {(data?.employees ?? []).map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.full_name} · {e.zone_code}
                      </option>
                    ))}
                  </select>
                  <label className="mt-2 flex items-center gap-2 text-[12px] text-fo-ink-secondary">
                    <input
                      type="checkbox"
                      checked={stableDefault}
                      onChange={(e) => setStableDefault(e.target.checked)}
                    />
                    Definir como afetação estável do plano
                  </label>
                </div>
                {timeEntry && (
                  <div>
                    <div className="mb-1.5 text-[12px] font-semibold text-fo-ink-muted">
                      Modelo das 7 horas
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      {HOUR_LABELS.map((h) => (
                        <div
                          key={h.key}
                          className="rounded-fo-sm border border-fo-border bg-fo-surface-raised px-2 py-1.5"
                        >
                          <div className="text-[11px] text-fo-ink-muted">{h.label}</div>
                          <div className="font-mono text-[14px] font-semibold">
                            {Number(timeEntry[h.key]).toFixed(1)}h
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {history.length > 0 && (
                  <div>
                    <div className="mb-1 text-[12px] font-semibold text-fo-ink-muted">
                      Histórico previsto vs executado
                    </div>
                    <ul className="space-y-1.5">
                      {history.map((h) => (
                        <li key={h.id} className="rounded-fo-sm border border-fo-border px-2 py-1.5 text-[12px]">
                          Previsto: <strong>{h.planned_employee_name}</strong>
                          <br />
                          Executado: <strong>{h.executed_employee_name}</strong>
                          <div className="text-fo-ink-muted">{h.reason}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2 border-t border-fo-border px-4 py-3">
            <button
              type="button"
              className="fo-btn-primary"
              disabled={!selected || !assignId || busyAction}
              onClick={() => void assignSelected()}
            >
              Afetar
            </button>
            <button
              type="button"
              className="fo-btn-secondary"
              disabled={!selected || !selected.assignments.length}
              onClick={() => setShowSubstModal(true)}
            >
              Substituir
            </button>
          </div>
        </aside>
      </div>

      {showSubstModal && selected && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-fo-ink/40 p-4">
          <div className="w-full max-w-md rounded-fo-lg border border-fo-border bg-fo-surface shadow-fo-md">
            <div className="flex items-center justify-between border-b border-fo-border px-4 py-3">
              <h3 className="font-bold">Substituição rápida</h3>
              <button type="button" className="fo-btn-ghost" onClick={() => setShowSubstModal(false)}>
                Fechar
              </button>
            </div>
            <div className="space-y-3 px-4 py-3 text-[13.5px]">
              <p className="text-fo-ink-secondary">
                Previsto: {selected.assignments[0]?.employee_name ?? "—"} · {selected.store_name}
              </p>
              <label className="block text-[12px] font-semibold text-fo-ink-muted">
                Substituto
                <select
                  className="fo-field mt-1 w-full"
                  value={substId}
                  onChange={(e) => setSubstId(e.target.value)}
                >
                  <option value="">— selecionar —</option>
                  {(data?.employees ?? [])
                    .filter((e) => e.id !== selected.assignments[0]?.employee_id)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.full_name} · {e.zone_code}
                      </option>
                    ))}
                </select>
              </label>
              <label className="block text-[12px] font-semibold text-fo-ink-muted">
                Motivo
                <input
                  className="fo-field mt-1 w-full"
                  value={substReason}
                  onChange={(e) => setSubstReason(e.target.value)}
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-fo-border px-4 py-3">
              <button type="button" className="fo-btn-secondary" onClick={() => setShowSubstModal(false)}>
                Cancelar
              </button>
              <button
                type="button"
                className="fo-btn-primary"
                disabled={!substId || busyAction}
                onClick={() => void substituteSelected()}
              >
                Confirmar exceção
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
