import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Organization } from "@/api/types";

export function SettingsPage() {
  const { token } = useAuth();
  const [org, setOrg] = useState<Organization | null>(null);
  const [roles, setRoles] = useState<{ code: string; name: string; description?: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    if (!token) return;
    const [o, r] = await Promise.all([
      apiFetch<Organization>("/organization", { token }),
      apiFetch<{ code: string; name: string; description?: string }[]>("/meta/roles", { token }),
    ]);
    setOrg(o);
    setRoles(r);
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function toggleSoftBlock() {
    if (!token || !org) return;
    const next = !Boolean(org.settings?.soft_block_docs_on_assign);
    const updated = await apiFetch<Organization>("/organization", {
      method: "PATCH",
      token,
      body: JSON.stringify({
        settings: { ...org.settings, soft_block_docs_on_assign: next },
      }),
    });
    setOrg(updated);
    setMsg(
      next
        ? "Soft-block docs ativo — afetação bloqueada se docs expirados (REC-07)."
        : "Soft-block docs desativado.",
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Definições</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">Organização, REC-07 e perfis RBAC (7).</p>
      </div>
      {msg && (
        <div className="rounded-fo bg-fo-brand-subtle px-3 py-2 text-[13px] text-fo-brand">{msg}</div>
      )}
      {org && (
        <div className="fo-panel p-4 space-y-3">
          <h2 className="font-bold">{org.name}</h2>
          <p className="text-[13px] text-fo-ink-muted">Timezone: {org.timezone}</p>
          <label className="flex items-center gap-2 text-[13px]">
            <input
              type="checkbox"
              checked={Boolean(org.settings?.soft_block_docs_on_assign)}
              onChange={() => void toggleSoftBlock()}
            />
            Soft-block documentos expirados na afetação (REC-07)
          </label>
          <pre className="overflow-auto rounded-fo bg-fo-surface-raised p-3 font-mono text-[12px]">
            {JSON.stringify(org.settings, null, 2)}
          </pre>
        </div>
      )}
      <div className="fo-panel overflow-hidden">
        <div className="border-b border-fo-border px-4 py-3 font-bold">Perfis RBAC</div>
        <ul>
          {roles.map((r) => (
            <li key={r.code} className="border-b border-fo-border px-4 py-3 last:border-0">
              <div className="font-semibold">{r.name}</div>
              <div className="font-mono text-[12px] text-fo-ink-muted">{r.code}</div>
              <div className="text-[13px] text-fo-ink-secondary">{r.description}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
