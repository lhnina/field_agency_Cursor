import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/api/auth";

export function LoginPage() {
  const { token, login } = useAuth();
  const [email, setEmail] = useState("admin@fieldops.pt");
  const [password, setPassword] = useState("fieldops");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (token) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no login");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-fo-canvas px-4">
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(ellipse at 20% 10%, #E6F3EF 0%, transparent 45%), radial-gradient(ellipse at 90% 80%, #FDF3E6 0%, transparent 40%)",
        }}
      />
      <form
        onSubmit={onSubmit}
        className="relative w-full max-w-md rounded-fo-lg border border-fo-border bg-fo-surface p-8 shadow-fo-md"
      >
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-fo bg-fo-brand text-sm font-bold text-white">
            FO
          </div>
          <div>
            <h1 className="text-[22px] font-bold tracking-tight">FieldOps</h1>
            <p className="text-[13px] text-fo-ink-muted">Back-office · demo PT</p>
          </div>
        </div>
        <label className="mb-3 block text-[12px] font-semibold text-fo-ink-secondary">
          Email
          <input
            className="fo-field mt-1 w-full"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="mb-4 block text-[12px] font-semibold text-fo-ink-secondary">
          Palavra-passe
          <input
            className="fo-field mt-1 w-full"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <div className="mb-3 rounded-fo bg-fo-danger-subtle px-3 py-2 text-[13px] text-fo-danger">
            {error}
          </div>
        )}
        <button type="submit" className="fo-btn-primary w-full" disabled={busy}>
          {busy ? "A entrar…" : "Entrar"}
        </button>
        <p className="mt-4 text-[12px] text-fo-ink-muted">
          Demo: <span className="font-mono">admin@fieldops.pt</span> /{" "}
          <span className="font-mono">fieldops</span>
        </p>
      </form>
    </div>
  );
}
