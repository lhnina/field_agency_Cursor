import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { RetailChain, Store, Zone } from "@/api/types";

export function StoresPage() {
  const { token } = useAuth();
  const [chains, setChains] = useState<RetailChain[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [zoneCode, setZoneCode] = useState("");
  const [zoneName, setZoneName] = useState("");
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    if (!token) return;
    const [c, s, z] = await Promise.all([
      apiFetch<RetailChain[]>("/retail-chains", { token }),
      apiFetch<Store[]>("/stores", { token }),
      apiFetch<Zone[]>("/zones", { token }),
    ]);
    setChains(c);
    setStores(s);
    setZones(z);
  }

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : "Erro"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function addZone() {
    if (!token || !zoneCode.trim()) return;
    setError(null);
    try {
      await apiFetch("/zones", {
        method: "POST",
        token,
        body: JSON.stringify({ code: zoneCode.trim(), name: zoneName.trim() || zoneCode.trim() }),
      });
      setZoneCode("");
      setZoneName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha zona");
    }
  }

  async function importCsv(file: File) {
    if (!token) return;
    setError(null);
    setImportMsg(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/v1/stores/import-csv", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "Import falhou");
      }
      const data = (await res.json()) as { created: number; skipped: number };
      setImportMsg(`Importadas ${data.created} · ignoradas ${data.skipped}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha CSV");
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Cadeias & lojas</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">
          Catálogo de zonas (Q05) · import CSV lojas (Q34).
        </p>
      </div>
      {error && (
        <div className="rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">{error}</div>
      )}
      {importMsg && (
        <div className="rounded-fo bg-fo-success-subtle px-3 py-2 text-[13px] text-fo-success">
          {importMsg}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[1fr_1.4fr]">
        <div className="fo-panel p-4 space-y-3">
          <h2 className="font-bold">Zonas</h2>
          <ul className="space-y-1 text-[13px]">
            {zones.map((z) => (
              <li key={z.id} className="flex justify-between border-b border-fo-border py-1.5 last:border-0">
                <span className="font-semibold">{z.code}</span>
                <span className="text-fo-ink-muted">{z.name}</span>
              </li>
            ))}
            {!zones.length && <li className="text-fo-ink-muted">Sem zonas.</li>}
          </ul>
          <div className="flex flex-wrap gap-2 pt-2">
            <input
              className="fo-field"
              placeholder="Código"
              value={zoneCode}
              onChange={(e) => setZoneCode(e.target.value)}
            />
            <input
              className="fo-field"
              placeholder="Nome"
              value={zoneName}
              onChange={(e) => setZoneName(e.target.value)}
            />
            <button type="button" className="fo-btn-secondary" onClick={() => void addZone()}>
              Adicionar
            </button>
          </div>
          <div className="border-t border-fo-border pt-3">
            <div className="mb-2 text-[12px] text-fo-ink-muted">
              CSV: chain,name,zone_code[,credential_name,address]
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void importCsv(f);
                e.target.value = "";
              }}
            />
            <button type="button" className="fo-btn-primary" onClick={() => fileRef.current?.click()}>
              Importar CSV lojas
            </button>
          </div>
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
    </div>
  );
}
