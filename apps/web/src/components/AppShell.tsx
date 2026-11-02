import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  CalendarDays,
  Users,
  FileText,
  BarChart3,
  Building2,
  Store,
  Settings,
  Bell,
  Search,
  LogOut,
  CalendarOff,
  Clock3,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/api/auth";
import { initials } from "@/lib/labels";

const NAV = [
  {
    section: "Operações",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/planeamento", label: "Planeamento", icon: CalendarDays },
      { to: "/ausencias", label: "Ausências", icon: CalendarOff },
      { to: "/horas", label: "Validação horas", icon: Clock3 },
      { to: "/colaboradores", label: "Colaboradores", icon: Users },
      { to: "/contratos", label: "Contratos", icon: FileText },
    ],
  },
  {
    section: "Cadastro",
    items: [
      { to: "/clientes", label: "Clientes & marcas", icon: Building2 },
      { to: "/lojas", label: "Cadeias & lojas", icon: Store },
    ],
  },
  {
    section: "Gestão",
    items: [
      { to: "/faturacao", label: "Pré-faturação / PHC", icon: Wallet },
      { to: "/rentabilidade", label: "Rentabilidade", icon: BarChart3 },
      { to: "/definicoes", label: "Definições", icon: Settings },
    ],
  },
];

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[var(--fo-sidebar-w)_1fr]">
      <aside className="sticky top-0 flex h-screen flex-col overflow-y-auto border-r border-fo-sidebar-border bg-fo-sidebar-bg">
        <div className="flex items-center gap-2.5 border-b border-fo-sidebar-border px-5 py-4">
          <div className="grid h-8 w-8 place-items-center rounded-fo bg-fo-brand text-[13px] font-bold text-white">
            FO
          </div>
          <div>
            <div className="text-base font-bold tracking-tight">FieldOps</div>
            <div className="text-[11px] font-medium text-fo-ink-muted">Atlantic Ops</div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-3">
          {NAV.map((group) => (
            <div key={group.section} className="mb-3">
              <div className="px-2.5 pb-1.5 text-[10px] font-bold uppercase tracking-[0.06em] text-fo-ink-muted">
                {group.section}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      [
                        "mb-0.5 flex items-center gap-2.5 rounded-fo px-2.5 py-2 text-[13.5px] font-medium transition-colors duration-fo",
                        isActive
                          ? "bg-fo-brand-subtle font-semibold text-fo-brand"
                          : "text-fo-ink-secondary hover:bg-[#eef2f5] hover:text-fo-ink",
                      ].join(" ")
                    }
                  >
                    <Icon size={16} />
                    {item.label}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-fo-sidebar-border px-3 py-3 text-xs text-fo-ink-muted">
          MVP · PR1 foundation
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex h-header items-center gap-4 border-b border-fo-border bg-fo-surface px-6">
          <div className="hidden items-center gap-2 rounded-fo border border-fo-border bg-fo-surface-raised px-2.5 py-1.5 text-[13px] font-medium sm:inline-flex">
            Semana 45 · nov 2026
          </div>
          <div className="flex max-w-sm flex-1 items-center gap-2 rounded-fo border border-fo-border px-3 py-2 text-[13px] text-fo-ink-muted">
            <Search size={14} />
            <input
              className="w-full border-0 bg-transparent text-fo-ink outline-none placeholder:text-fo-ink-muted"
              placeholder="Pesquisar loja, colaborador, contrato…"
            />
          </div>
          <div className="ml-auto flex items-center gap-2.5">
            <button type="button" className="relative grid h-9 w-9 place-items-center rounded-fo border border-fo-border bg-fo-surface hover:bg-fo-surface-raised" aria-label="Notificações">
              <Bell size={16} />
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full border-2 border-fo-surface bg-fo-danger" />
            </button>
            <div className="flex items-center gap-2.5 rounded-fo px-1 py-1">
              <div className="grid h-8 w-8 place-items-center rounded-fo bg-fo-brand-subtle text-[12px] font-bold text-fo-brand">
                {user ? initials(user.full_name) : "?"}
              </div>
              <div className="hidden leading-tight sm:block">
                <div className="text-[13px] font-semibold">{user?.full_name}</div>
                <div className="text-[11px] text-fo-ink-muted">{user?.roles?.[0] ?? "—"}</div>
              </div>
              <button type="button" onClick={logout} className="fo-btn-ghost px-2" title="Terminar sessão">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </header>
        <main className="flex-1 p-5 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
