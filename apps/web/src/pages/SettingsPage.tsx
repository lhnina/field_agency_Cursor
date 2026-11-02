import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Organization } from "@/api/types";

export function SettingsPage() {
  const { token } = useAuth();
  const [org, setOrg] = useState<Organization | null>(null);
  const [roles, setRoles] = useState<{ code: string; name: string; description?: string }[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetch<Organization>("/organization", { token }),
      apiFetch<{ code: string; name: string; description?: string }[]>("/meta/roles", { token }),
    ]).then(([o, r]) => {
      setOrg(o);
      setRoles(r);
    });
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Definições</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">Organização e perfis RBAC (7).</p>
      </div>
      {org && (
        <div className="fo-panel p-4">
          <h2 className="font-bold">{org.name}</h2>
          <p className="text-[13px] text-fo-ink-muted">Timezone: {org.timezone}</p>
          <pre className="mt-3 overflow-auto rounded-fo bg-fo-surface-raised p-3 font-mono text-[12px]">
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
