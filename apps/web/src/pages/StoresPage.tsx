import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { RetailChain, Store } from "@/api/types";

export function StoresPage() {
  const { token } = useAuth();
  const [chains, setChains] = useState<RetailChain[]>([]);
  const [stores, setStores] = useState<Store[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetch<RetailChain[]>("/retail-chains", { token }),
      apiFetch<Store[]>("/stores", { token }),
    ]).then(([c, s]) => {
      setChains(c);
      setStores(s);
    });
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Cadeias & lojas</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">Insígnia, credencial e zona.</p>
      </div>
      <div className="fo-panel overflow-hidden">
        <table className="w-full text-left text-[13px]">
          <thead className="border-b border-fo-border bg-fo-surface-raised text-[11px] font-bold uppercase tracking-[0.03em] text-fo-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Loja</th>
              <th className="px-4 py-2.5">Cadeia</th>
              <th className="px-4 py-2.5">Credencial</th>
              <th className="px-4 py-2.5">Zona</th>
            </tr>
          </thead>
          <tbody>
            {stores.map((s) => (
              <tr key={s.id} className="border-b border-fo-border last:border-0">
                <td className="px-4 py-3 font-semibold">{s.name}</td>
                <td className="px-4 py-3">
                  {chains.find((c) => c.id === s.retail_chain_id)?.name ?? "—"}
                </td>
                <td className="px-4 py-3">{s.credential_name ?? "—"}</td>
                <td className="px-4 py-3">{s.zone_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
