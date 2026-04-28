import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <main className="login-shell">
      <section className="login-panel" aria-labelledby="login-title">
        <div>
          <p className="eyebrow">Operator Access</p>
          <h1 id="login-title">Trading System Monitor</h1>
          <p className="muted">
            Enter the dashboard access token configured in Vercel. Tokens stay server-side and are not stored in browser storage.
          </p>
        </div>
        <LoginForm />
      </section>
    </main>
  );
}
