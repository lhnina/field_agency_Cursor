import { useEffect, useMemo, useState } from "react";
import { addDays, format, parseISO, startOfWeek } from "date-fns";
import { pt } from "date-fns/locale";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { PlanningWeek, Shift, TimeEntry } from "@/api/types";
import { CONTRACT_TYPE_LABEL, HOUR_LABELS, initials, shortType, slotClass } from "@/lib/labels";

const WEEK_ANCHOR = "2026-11-02";

function fmtHour(iso: string) {
  return format(parseISO(iso), "HH:mm");
}

export function PlanningPage() {
  const { token } = useAuth();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(parseISO(WEEK_ANCHOR), { weekStartsOn: 1 }));
  const [data, setData] = useState<PlanningWeek | null>(null);
  const [selected, setSelected] = useState<Shift | null>(null);
  const [timeEntry, setTimeEntry] = useState<TimeEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyGen, setBusyGen] = useState(false);

  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  async function load() {
    if (!token) return;
    setError(null);
    try {
      const ws = format(weekStart, "yyyy-MM-dd");
      const week = await apiFetch<PlanningWeek>(`/planning/week?week_start=${ws}`, { token });
      setData(week);
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
      return;
    }
    apiFetch<TimeEntry>(`/shifts/${selected.id}/time-entry`, { token })
      .then(setTimeEntry)
      .catch(() => setTimeEntry(null));
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

  const rows = useMemo(() => {
    if (!data) return [];
    const byEmployee = new Map<string, { name: string; meta: string; shifts: Shift[] }>();
    for (const emp of data.employees) {
      byEmployee.set(emp.id, {
        name: emp.full_name,
        meta: `${emp.zone_code} · ${emp.engagement_type}`,
        shifts: [],
      });
    }
    const unassigned: Shift[] = [];
    for (const shift of data.shifts) {
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
      meta: "Fila de slots",
      shifts: unassigned,
    });
    return result;
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">Planeamento de serviços</h1>
          <p className="text-[13.5px] text-fo-ink-secondary">
            Vista por colaboradores · {format(weekStart, "d MMM", { locale: pt })} –{" "}
            {format(addDays(weekStart, 6), "d MMM yyyy", { locale: pt })}
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
          <button type="button" className="fo-btn-accent" disabled title="PR2">
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
        <span className="fo-badge bg-fo-brand-subtle text-fo-brand">Reposição</span>
        <span className="fo-badge bg-fo-info-subtle text-fo-info">Promoção</span>
        <span className="fo-badge bg-[#efeaf8] text-fo-logistica">Logística</span>
        <span className="fo-badge bg-fo-accent-subtle text-fo-accent-hover">Por atribuir</span>
      </div>

      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}

      <div className="grid gap-3 xl:grid-cols-[1fr_320px]">
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
              {rows.map((row) => (
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
                  {days.map((day) => {
                    const key = format(day, "yyyy-MM-dd");
                    const dayShifts = row.shifts.filter(
                      (s) => format(parseISO(s.planned_start), "yyyy-MM-dd") === key,
                    );
                    return (
                      <td key={key} className="px-1.5 py-2">
                        <div className="flex flex-col gap-1.5">
                          {dayShifts.map((shift) => {
                            const unassigned = shift.assignments.length === 0;
                            const storeShort = (shift.store_name ?? "").split(" ").slice(-1)[0] ?? "";
                            return (
                              <button
                                key={shift.id}
                                type="button"
                                className={`${slotClass(shift.shift_type, unassigned)} text-left ${
                                  selected?.id === shift.id ? "ring-2 ring-fo-brand" : ""
                                }`}
                                onClick={() => setSelected(shift)}
                              >
                                {shortType(shift.shift_type)} · {storeShort}
                                <br />
                                {fmtHour(shift.planned_start).slice(0, 5)}–
                                {fmtHour(shift.planned_end).slice(0, 5)}
                                {unassigned ? " · s/ recurso" : ""}
                              </button>
                            );
                          })}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
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
                Clique num serviço no calendário para ver estado, afetação e as 7 horas.
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
                  <div className="text-[12px] font-semibold text-fo-ink-muted">Colaborador</div>
                  <div>
                    {selected.assignments[0]?.employee_name ?? (
                      <span className="text-fo-accent-hover">Sem recurso</span>
                    )}
                  </div>
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
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2 border-t border-fo-border px-4 py-3">
            <button type="button" className="fo-btn-primary" disabled>
              Afetar
            </button>
            <button type="button" className="fo-btn-secondary" disabled>
              Substituir
            </button>
            <button type="button" className="fo-btn-ghost" disabled>
              Histórico
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
