import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/api/auth";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { PlanningPage } from "@/pages/PlanningPage";
import { EmployeesPage } from "@/pages/EmployeesPage";
import { ContractsPage } from "@/pages/ContractsPage";
import { ClientsPage } from "@/pages/ClientsPage";
import { StoresPage } from "@/pages/StoresPage";
import { ProfitabilityPage } from "@/pages/ProfitabilityPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AbsencesPage } from "@/pages/AbsencesPage";
import { HoursPage } from "@/pages/HoursPage";
import { BillingPage } from "@/pages/BillingPage";

function Protected({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();
  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center text-fo-ink-secondary">
        A carregar…
      </div>
    );
  }
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="planeamento" element={<PlanningPage />} />
        <Route path="ausencias" element={<AbsencesPage />} />
        <Route path="horas" element={<HoursPage />} />
        <Route path="colaboradores" element={<EmployeesPage />} />
        <Route path="contratos" element={<ContractsPage />} />
        <Route path="clientes" element={<ClientsPage />} />
        <Route path="lojas" element={<StoresPage />} />
        <Route path="faturacao" element={<BillingPage />} />
        <Route path="rentabilidade" element={<ProfitabilityPage />} />
        <Route path="definicoes" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
