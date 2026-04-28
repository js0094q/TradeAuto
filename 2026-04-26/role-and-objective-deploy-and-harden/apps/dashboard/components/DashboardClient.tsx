"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Lock,
  LogOut,
  Power,
  RefreshCw,
  Shield,
  StopCircle,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { HealthPayload, MetricsPayload, ProxyEnvelope, ReadinessPayload } from "@/lib/types";

type DashboardClientProps = {
  backendLabel: string;
  controlActionsEnabled: boolean;
};

type SnapshotState = {
  health?: ProxyEnvelope<HealthPayload>;
  readiness?: ProxyEnvelope<ReadinessPayload>;
  metrics?: ProxyEnvelope<MetricsPayload>;
  lastUpdated?: string;
  loading: boolean;
  error?: string;
};

const emptySnapshot: SnapshotState = {
  loading: true,
};

export function DashboardClient({ backendLabel, controlActionsEnabled }: DashboardClientProps) {
  const [snapshot, setSnapshot] = useState<SnapshotState>(emptySnapshot);
  const [controlMessage, setControlMessage] = useState<string | null>(null);
  const [killConfirm, setKillConfirm] = useState("");
  const [resumeConfirm, setResumeConfirm] = useState("");
  const [controlBusy, setControlBusy] = useState<string | null>(null);

  async function loadSnapshot() {
    setSnapshot((current) => ({ ...current, loading: true, error: undefined }));
    try {
      const [health, readiness, metrics] = await Promise.all([
        fetchEnvelope<HealthPayload>("/api/backend/health"),
        fetchEnvelope<ReadinessPayload>("/api/backend/ready"),
        fetchEnvelope<MetricsPayload>("/api/backend/metrics"),
      ]);
      setSnapshot({
        health,
        readiness,
        metrics,
        lastUpdated: new Date().toLocaleString(),
        loading: false,
      });
    } catch (error) {
      setSnapshot((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "Dashboard refresh failed",
      }));
    }
  }

  useEffect(() => {
    void loadSnapshot();
    const interval = window.setInterval(() => void loadSnapshot(), 30000);
    return () => window.clearInterval(interval);
  }, []);

  const healthOk = snapshot.health?.ok && snapshot.health.data?.ok;
  const readyOk = snapshot.readiness?.ok && snapshot.readiness.data?.ok;
  const readinessChecks = snapshot.readiness?.data?.checks || [];
  const failedChecks = readinessChecks.filter((check) => !check.ok);
  const metrics = snapshot.metrics?.data;
  const killSwitchState = metrics?.kill_switch_state || "unknown";

  const posture = useMemo(
    () => [
      {
        label: "API",
        value: healthOk ? "Healthy" : "Unverified",
        tone: healthOk ? "good" : "bad",
        detail: snapshot.health?.error || snapshot.health?.data?.service || "Waiting for health",
        icon: Activity,
      },
      {
        label: "Readiness",
        value: readyOk ? "Ready" : "Blocked",
        tone: readyOk ? "good" : "warn",
        detail: readinessSummary(readinessChecks, snapshot.readiness?.error),
        icon: CheckCircle2,
      },
      {
        label: "Kill Switch",
        value: titleCase(killSwitchState),
        tone: killSwitchState === "enabled" ? "warn" : killSwitchState === "disabled" ? "good" : "neutral",
        detail: killSwitchState === "enabled" ? "New trading remains blocked" : "Runtime state from metrics",
        icon: Shield,
      },
      {
        label: "Controls",
        value: controlActionsEnabled ? "Enabled" : "Read-only",
        tone: controlActionsEnabled ? "warn" : "neutral",
        detail: controlActionsEnabled ? "Confirmation still required" : "Vercel env blocks mutations",
        icon: Lock,
      },
    ],
    [
      controlActionsEnabled,
      healthOk,
      killSwitchState,
      readinessChecks,
      readyOk,
      snapshot.health,
      snapshot.readiness?.error,
    ],
  );

  async function sendControl(path: "admin/kill" | "admin/resume", confirmation: string) {
    setControlBusy(path);
    setControlMessage(null);
    try {
      const result = await fetchEnvelope(`/api/backend/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation }),
      });
      setControlMessage(result.ok ? `${path} accepted` : result.error || `${path} rejected`);
      await loadSnapshot();
    } finally {
      setControlBusy(null);
    }
  }

  async function logout() {
    await fetch("/api/session", { method: "DELETE" });
    window.location.assign("/login");
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">VPS: {backendLabel}</p>
          <h1>Trading System Monitor</h1>
        </div>
        <div className="topbar-actions">
          <span className={`status-chip ${healthOk ? "good" : "bad"}`}>
            <span aria-hidden="true" />
            {healthOk ? "Online" : "Attention"}
          </span>
          <button className="icon-button" type="button" onClick={() => void loadSnapshot()} disabled={snapshot.loading}>
            <RefreshCw size={16} aria-hidden="true" />
            Refresh
          </button>
          <button className="icon-button secondary" type="button" onClick={() => void logout()}>
            <LogOut size={16} aria-hidden="true" />
            Sign out
          </button>
        </div>
      </header>

      <section className="status-strip" aria-label="Service posture">
        {posture.map((item) => (
          <article className="posture-card" key={item.label}>
            <div className="posture-heading">
              <item.icon size={18} aria-hidden="true" />
              <span>{item.label}</span>
            </div>
            <strong className={item.tone}>{item.value}</strong>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>

      <section className="dashboard-grid">
        <section className="panel checks-panel" aria-labelledby="checks-title">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Readiness</p>
              <h2 id="checks-title">Runtime Checks</h2>
            </div>
            <span className="timestamp">{snapshot.lastUpdated || "Not refreshed"}</span>
          </div>
          {snapshot.error ? <p className="alert bad">{snapshot.error}</p> : null}
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Check</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {readinessChecks.length ? (
                  readinessChecks.map((check) => (
                    <tr key={check.name}>
                      <td>
                        <StatusIcon ok={check.ok} />
                      </td>
                      <td>{formatName(check.name)}</td>
                      <td>{formatDetail(check.detail)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3}>{snapshot.readiness?.error || "Readiness data has not loaded."}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel control-panel" aria-labelledby="controls-title">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Guarded Mutations</p>
              <h2 id="controls-title">Operator Controls</h2>
            </div>
          </div>
          <p className="muted compact">
            Actions route through Vercel server functions. The browser never receives the VPS admin token.
          </p>
          <ControlBlock
            title="Enable Kill Switch"
            detail="Protective stop. Requires ENABLE_KILL_SWITCH."
            phrase="ENABLE_KILL_SWITCH"
            value={killConfirm}
            setValue={setKillConfirm}
            disabled={!controlActionsEnabled || controlBusy !== null}
            busy={controlBusy === "admin/kill"}
            icon="stop"
            onSubmit={() => sendControl("admin/kill", killConfirm)}
          />
          <ControlBlock
            title="Resume Trading"
            detail="Disables kill switch only if backend readiness passes. Requires YES_I_UNDERSTAND."
            phrase="YES_I_UNDERSTAND"
            value={resumeConfirm}
            setValue={setResumeConfirm}
            disabled={!controlActionsEnabled || controlBusy !== null}
            busy={controlBusy === "admin/resume"}
            icon="power"
            onSubmit={() => sendControl("admin/resume", resumeConfirm)}
          />
          {!controlActionsEnabled ? (
            <p className="alert neutral">Control actions are disabled by `DASHBOARD_ALLOW_CONTROL_ACTIONS=false`.</p>
          ) : null}
          {controlMessage ? <p className="alert neutral">{controlMessage}</p> : null}
        </aside>
      </section>

      <section className="metrics-grid" aria-label="Runtime metrics">
        <Metric label="Mode" value={metrics?.trading_mode || "unknown"} />
        <Metric label="Uptime" value={formatDuration(metrics?.uptime_seconds || snapshot.health?.data?.uptime_seconds)} />
        <Metric label="Broker" value={metrics?.broker_account_status || "unknown"} />
        <Metric label="Market" value={metrics?.market_open_status || "unknown"} />
        <Metric label="Open Positions" value={formatNullable(metrics?.open_positions)} />
        <Metric label="Open Orders" value={formatNullable(metrics?.open_orders)} />
        <Metric label="Risk Rejects" value={formatNullable(metrics?.risk_rejects)} />
        <Metric label="Strategy" value={metrics?.active_strategy || "none"} />
      </section>
    </main>
  );
}

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="status-cell good">
      <CheckCircle2 size={16} aria-hidden="true" />
      Pass
    </span>
  ) : (
    <span className="status-cell bad">
      <XCircle size={16} aria-hidden="true" />
      Fail
    </span>
  );
}

function ControlBlock(props: {
  title: string;
  detail: string;
  phrase: string;
  value: string;
  setValue: (value: string) => void;
  disabled: boolean;
  busy: boolean;
  icon: "stop" | "power";
  onSubmit: () => void;
}) {
  const Icon = props.icon === "stop" ? StopCircle : Power;
  return (
    <form
      className="control-block"
      onSubmit={(event) => {
        event.preventDefault();
        void props.onSubmit();
      }}
    >
      <div>
        <h3>{props.title}</h3>
        <p>{props.detail}</p>
      </div>
      <input
        value={props.value}
        onChange={(event) => props.setValue(event.target.value)}
        placeholder={props.phrase}
        disabled={props.disabled}
      />
      <button type="submit" disabled={props.disabled || props.value !== props.phrase}>
        <Icon size={16} aria-hidden="true" />
        {props.busy ? "Sending" : props.title}
      </button>
    </form>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

async function fetchEnvelope<T>(path: string, init?: RequestInit): Promise<ProxyEnvelope<T>> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const payload = (await response.json().catch(() => null)) as ProxyEnvelope<T> | null;
  if (!payload) {
    throw new Error(`Invalid response from ${path}`);
  }
  return payload;
}

function formatName(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function readinessSummary(
  checks: Array<{ ok: boolean; name: string; detail: string }>,
  fallbackError?: string,
) {
  if (!checks.length) {
    return fallbackError ? "No structured readiness payload" : "Waiting for readiness";
  }

  const failed = checks.filter((check) => !check.ok);
  if (!failed.length) {
    return `${checks.length} checks passing`;
  }
  return `${failed.length} blocked: ${formatName(failed[0].name)}`;
}

function formatDetail(value: string) {
  try {
    const parsed = JSON.parse(value) as { message?: string };
    if (typeof parsed.message === "string") {
      return parsed.message;
    }
  } catch {
    return value;
  }
  return value;
}

function titleCase(value: string) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNullable(value: number | null | undefined) {
  return value === null || value === undefined ? "unknown" : value.toString();
}

function formatDuration(value: number | undefined) {
  if (!value) {
    return "unknown";
  }
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}m ${seconds}s`;
}
