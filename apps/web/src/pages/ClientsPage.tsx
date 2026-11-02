import { useEffect, useState } from "react";
import { useAuth } from "@/api/auth";
import { apiFetch } from "@/api/client";
import type { Brand, Client } from "@/api/types";

export function ClientsPage() {
  const { token } = useAuth();
  const [clients, setClients] = useState<Client[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetch<Client[]>("/clients", { token }),
      apiFetch<Brand[]>("/brands", { token }),
    ]).then(([c, b]) => {
      setClients(c);
      setBrands(b);
    });
  }, [token]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Clientes & marcas</h1>
        <p className="text-[13.5px] text-fo-ink-secondary">Cadastro comercial mínimo.</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Clientes</div>
          <ul>
            {clients.map((c) => (
              <li key={c.id} className="flex items-center justify-between border-b border-fo-border px-4 py-3 last:border-0">
                <div>
                  <div className="font-semibold">{c.name}</div>
                  <div className="font-mono text-[12px] text-fo-ink-muted">NIF {c.vat_number}</div>
                </div>
                <span className="fo-badge bg-fo-success-subtle text-fo-success">{c.status}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="fo-panel overflow-hidden">
          <div className="border-b border-fo-border px-4 py-3 font-bold">Marcas</div>
          <ul>
            {brands.map((b) => (
              <li key={b.id} className="border-b border-fo-border px-4 py-3 last:border-0">
                <div className="font-semibold">{b.name}</div>
                <div className="text-[12px] text-fo-ink-muted">
                  Cliente {clients.find((c) => c.id === b.client_id)?.name ?? "—"}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
