import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { AuditLog, EmailOutbox, Notification } from "@/api/types";

export function NotificationsPage() {
  const { token } = useAuth();
  const [notes, setNotes] = useState<Notification[]>([]);
  const [emails, setEmails] = useState<EmailOutbox[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);

  async function refresh() {
    if (!token) return;
    const [n, e, a] = await Promise.all([
      apiFetch<Notification[]>("/notifications", { token }),
      apiFetch<EmailOutbox[]>("/email-outbox", { token }),
      apiFetch<AuditLog[]>("/audit-logs?limit=40", { token }),
    ]);
    setNotes(n);
    setEmails(e);
    setAudit(a);
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function markRead(id: string) {
    if (!token) return;
    await apiFetch(`/notifications/${id}/read`, { method: "POST", token });
    await refresh();
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Notificações & auditoria</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          In-app + email stub (Q31) · log append-only (MVP-26).
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">In-app</div>
          <ul>
            {notes.map((n) => (
              <li key={n.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="flex justify-between gap-2">
                  <div>
                    <div className="font-semibold">
                      {!n.read && <span className="mr-1 inline-block h-2 w-2 rounded-full bg-fo-danger" />}
                      {n.title}
                    </div>
                    <div className="text-[12px] text-fo-ink-muted">
                      {n.kind} · {n.body}
                    </div>
                  </div>
                  {!n.read && (
                    <button type="button" className="fo-btn-ghost text-[12px]" onClick={() => void markRead(n.id)}>
                      Lida
                    </button>
                  )}
                </div>
              </li>
            ))}
            {!notes.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Sem notificações.</li>
            )}
          </ul>
        </div>
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Email stub</div>
          <ul>
            {emails.map((e) => (
              <li key={e.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="font-semibold">{e.subject}</div>
                <div className="text-[12px] text-fo-ink-muted">
                  → {e.to_address} · {e.status}
                </div>
              </li>
            ))}
            {!emails.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Outbox vazio.</li>
            )}
          </ul>
        </div>
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Audit log</div>
          <ul className="max-h-[28rem] overflow-auto">
            {audit.map((a) => (
              <li key={a.id} className="border-b border-fo-border px-4 py-2.5 last:border-0">
                <div className="font-mono text-[12px] font-semibold">{a.action}</div>
                <div className="text-[11px] text-fo-ink-muted">
                  {a.entity_type}:{a.entity_id.slice(0, 8)} ·{" "}
                  {new Date(a.created_at).toLocaleString("pt-PT")}
                </div>
              </li>
            ))}
            {!audit.length && (
              <li className="px-4 py-3 text-[13px] text-fo-ink-muted">Sem eventos.</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
