"use client";

import { Lock } from "lucide-react";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(payload?.error || "Login failed");
      setSubmitting(false);
      return;
    }

    const next = new URLSearchParams(window.location.search).get("next") || "/";
    window.location.assign(next.startsWith("/") ? next : "/");
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <label htmlFor="dashboard-token">Access token</label>
      <input
        id="dashboard-token"
        name="dashboard-token"
        type="password"
        autoComplete="current-password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        placeholder="Enter token"
      />
      {error ? <p className="form-error">{error}</p> : null}
      <button type="submit" disabled={submitting || !token.trim()}>
        <Lock size={16} aria-hidden="true" />
        {submitting ? "Checking" : "Open dashboard"}
      </button>
    </form>
  );
}
