"use client";

import {
  Activity,
  CheckCircle2,
  Lock,
  LogOut,
  Power,
  PlayCircle,
  Radar,
  RefreshCw,
  Shield,
  StopCircle,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type {
  HealthPayload,
  MetricsPayload,
  PaperStrategyPayload,
  PaperStrategySnapshot,
  ProxyEnvelope,
  ReadinessPayload,
} from "@/lib/types";

type DashboardClientProps = {
  backendLabel: string;
  controlActionsEnabled: boolean;
};

type Tone = "good" | "warn" | "bad" | "neutral";

type SnapshotState = {
  health?: ProxyEnvelope<HealthPayload>;
  readiness?: ProxyEnvelope<ReadinessPayload>;
  metrics?: ProxyEnvelope<MetricsPayload>;
  paperStrategy?: ProxyEnvelope<PaperStrategyPayload>;
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
  const [paperCycleConfirm, setPaperCycleConfirm] = useState("");
  const [controlBusy, setControlBusy] = useState<string | null>(null);

  async function loadSnapshot() {
    setSnapshot((current) => ({ ...current, loading: true, error: undefined }));
    try {
      const [health, readiness, metrics, paperStrategy] = await Promise.all([
        fetchEnvelope<HealthPayload>("/api/backend/health"),
        fetchEnvelope<ReadinessPayload>("/api/backend/ready"),
        fetchEnvelope<MetricsPayload>("/api/backend/metrics"),
        fetchEnvelope<PaperStrategyPayload>("/api/backend/paper-strategy"),
      ]);
      setSnapshot({
        health,
        readiness,
        metrics,
        paperStrategy,
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
  const metrics = snapshot.metrics?.data;
  const killSwitchState = metrics?.kill_switch_state || "unknown";
  const paperStrategy = snapshot.paperStrategy?.data;
  const paperStrategies = paperStrategy?.strategies || [];
  const paperExecution = paperStrategy?.paper_execution || undefined;
  const primaryPaperStrategy = paperStrategies[0];
  const paperStrategyOk = Boolean(snapshot.paperStrategy?.ok && paperStrategy?.ok);

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
        label: "Paper Engine",
        value: metrics?.paper_engine_running ? "Running" : "Stopped",
        tone: metrics?.paper_engine_running ? "good" : "warn",
        detail: paperStrategySummary(paperStrategy, snapshot.paperStrategy?.error),
        icon: Radar,
      },
      {
        label: "Live Engine",
        value: metrics?.live_engine_running ? "Running" : "Stopped",
        tone: metrics?.live_engine_running ? "good" : "warn",
        detail: metrics?.latest_live_error ? "Recent live startup errors detected" : "No recent live engine error line",
        icon: Activity,
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
      metrics?.latest_live_error,
      metrics?.live_engine_running,
      metrics?.paper_engine_running,
      paperStrategy,
      readinessChecks,
      readyOk,
      snapshot.health,
      snapshot.paperStrategy?.error,
      snapshot.readiness?.error,
    ],
  );

  async function sendControl(path: "admin/kill" | "admin/resume" | "admin/paper-cycle", confirmation: string) {
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
          <ControlBlock
            title="Run Paper Cycle"
            detail="Runs one immediate paper strategy cycle on VPS. Requires RUN_PAPER_CYCLE."
            phrase="RUN_PAPER_CYCLE"
            value={paperCycleConfirm}
            setValue={setPaperCycleConfirm}
            disabled={!controlActionsEnabled || controlBusy !== null}
            busy={controlBusy === "admin/paper-cycle"}
            icon="play"
            onSubmit={() => sendControl("admin/paper-cycle", paperCycleConfirm)}
          />
          {!controlActionsEnabled ? (
            <p className="alert neutral">Control actions are disabled by `DASHBOARD_ALLOW_CONTROL_ACTIONS=false`.</p>
          ) : null}
          {controlMessage ? <p className="alert neutral">{controlMessage}</p> : null}
        </aside>
      </section>

      <section className="panel strategy-panel" aria-labelledby="paper-strategy-title">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Paper Strategy</p>
            <h2 id="paper-strategy-title">Current Paper Cycle</h2>
          </div>
          <span className="timestamp">{formatTimestamp(paperStrategy?.timestamp || paperStrategy?.file_updated_at)}</span>
        </div>
        {paperStrategy?.message ? <p className={`alert ${paperStrategy.ok ? "neutral" : "warn"}`}>{paperStrategy.message}</p> : null}
        <div className="strategy-summary-grid">
          <StrategyStat label="Mode" value={paperStrategy?.mode || "paper"} tone={paperStrategyOk ? "good" : "neutral"} />
          <StrategyStat label="Execution" value={formatName(paperExecution?.status || "unknown")} tone={executionTone(paperExecution?.status)} />
          <StrategyStat label="Selected" value={countSelected(paperStrategies).toString()} tone={countSelected(paperStrategies) ? "good" : "neutral"} />
          <StrategyStat label="Risk Blocks" value={countRiskBlocks(paperStrategies, paperExecution).toString()} tone={countRiskBlocks(paperStrategies, paperExecution) ? "warn" : "good"} />
        </div>
        <div className="execution-strip">
          <span>Entries {paperExecution?.enabled ? "enabled" : "disabled"}</span>
          <span>Runtime gate {paperExecution?.runtime_gate_passed ? "passed" : "not passed"}</span>
          <span>Market {paperExecution?.market_open ? "open" : "closed or unknown"}</span>
          <span>Order type {paperExecution?.order_type || "unknown"}</span>
          <span>Bankroll {formatCurrency(paperExecution?.bankroll_usd)}</span>
          <span>Max order {formatCurrency(paperExecution?.max_notional_usd || paperExecution?.notional_usd)}</span>
          <span>Limit buffer {formatBps(paperExecution?.limit_buffer_bps)}</span>
        </div>
        <div className="table-shell strategy-table">
          <table>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Mode</th>
                <th>Regime</th>
                <th>Selected</th>
                <th>Orders</th>
                <th>Blocks</th>
              </tr>
            </thead>
            <tbody>
              {paperStrategies.length ? (
                paperStrategies.map((strategy) => (
                  <tr key={`${strategy.strategy_name}-${strategy.mode}`}>
                    <td>{formatName(strategy.strategy_name)}</td>
                    <td>{formatName(strategy.mode)}</td>
                    <td>{formatRegime(strategy)}</td>
                    <td>{formatSelected(strategy)}</td>
                    <td>{formatOrders(strategy)}</td>
                    <td>{formatBlocks(strategy.risk_blocks, strategy.warnings)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>{snapshot.paperStrategy?.error || paperStrategy?.message || "Paper strategy status has not loaded."}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {paperExecution?.orders?.length ? (
          <div className="table-shell strategy-table execution-orders">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Target</th>
                  <th>Current</th>
                  <th>Order</th>
                  <th>Qty</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {paperExecution.orders.map((order) => (
                  <tr key={`${order.client_order_id || order.symbol}-${order.status}`}>
                    <td>{order.symbol || "unknown"}</td>
                    <td>{formatName(order.status || "unknown")}</td>
                    <td>{formatCurrency(order.target_notional_usd)}</td>
                    <td>{formatCurrency(order.current_position_notional_usd)}</td>
                    <td>{formatCurrency(order.notional_usd)}</td>
                    <td>{formatQuantity(order.qty)}</td>
                    <td>{formatBlocks(order.risk_blocks)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="metrics-grid" aria-label="Runtime metrics">
        <Metric label="Mode" value={metrics?.trading_mode || "unknown"} />
        <Metric label="Uptime" value={formatDuration(metrics?.uptime_seconds || snapshot.health?.data?.uptime_seconds)} />
        <Metric label="Broker" value={metrics?.broker_account_status || "unknown"} />
        <Metric label="Market" value={metrics?.market_open_status || "unknown"} />
        <Metric label="Open Positions" value={formatNullable(metrics?.open_positions)} />
        <Metric label="Open Orders" value={formatNullable(metrics?.open_orders)} />
        <Metric label="Risk Rejects" value={formatNullable(metrics?.risk_rejects)} />
        <Metric label="Strategy" value={metrics?.active_strategy || primaryPaperStrategy?.strategy_name || "none"} />
        <Metric label="Paper Execution" value={formatName(metrics?.paper_execution_status || "unknown")} />
        <Metric label="Paper Gate" value={formatRuntimeGate(metrics?.paper_runtime_gate_passed, metrics?.paper_runtime_gate_blocks)} />
        <Metric label="Last Trade" value={formatTimestamp(metrics?.last_trade_time)} />
        <Metric label="API Process" value={formatRunning(metrics?.api_process_running)} />
        <Metric label="Paper Process" value={formatRunning(metrics?.paper_engine_running)} />
        <Metric label="Live Process" value={formatRunning(metrics?.live_engine_running)} />
        <Metric label="Telegram Process" value={formatRunning(metrics?.telegram_bot_running)} />
      </section>
      <section className="panel" aria-labelledby="runtime-alerts-title">
        <div className="panel-header">
          <div>
            <p className="eyebrow">VPS Runtime Alerts</p>
            <h2 id="runtime-alerts-title">Latest Error Signals</h2>
          </div>
        </div>
        <p className="muted compact">{metrics?.latest_api_error || "API: no recent error line"}</p>
        <p className="muted compact">{metrics?.latest_paper_error || "Paper: no recent error line"}</p>
        <p className="muted compact">{metrics?.latest_live_error || "Live: no recent error line"}</p>
        <p className="muted compact">{metrics?.last_telegram_alert_time || "Telegram: no recent warning line"}</p>
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
  icon: "stop" | "power" | "play";
  onSubmit: () => void;
}) {
  const Icon = props.icon === "stop" ? StopCircle : props.icon === "play" ? PlayCircle : Power;
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

function StrategyStat({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <article className="strategy-stat">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
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

function paperStrategySummary(payload: PaperStrategyPayload | undefined, fallbackError?: string) {
  if (fallbackError) {
    return fallbackError;
  }
  if (!payload) {
    return "Waiting for strategy status";
  }
  if (!payload.ok) {
    return payload.message || "No current paper cycle";
  }
  const selected = countSelected(payload.strategies || []);
  const when = formatTimestamp(payload.timestamp || payload.file_updated_at);
  return `${selected} selections from ${when}`;
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

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "Not refreshed";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
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

function formatCurrency(value: number | undefined) {
  return value === undefined ? "unknown" : `$${value.toFixed(2)}`;
}

function formatBps(value: number | undefined) {
  return value === undefined ? "unknown" : `${value.toFixed(0)} bps`;
}

function formatQuantity(value: number | undefined) {
  return value === undefined ? "unknown" : value.toFixed(4);
}

function formatRunning(value: boolean | undefined) {
  if (value === undefined) {
    return "unknown";
  }
  return value ? "running" : "stopped";
}

function formatRuntimeGate(passed: boolean | null | undefined, blocks?: string[]) {
  if (passed === true) {
    return "passed";
  }
  if (passed === false) {
    return blocks?.length ? `blocked (${blocks.length})` : "blocked";
  }
  return "unknown";
}

function executionTone(status: string | undefined): Tone {
  if (!status || status === "disabled" || status === "no_entries") {
    return "neutral";
  }
  if (status === "complete" || status === "submitted") {
    return "good";
  }
  if (status.startsWith("blocked")) {
    return "warn";
  }
  return "bad";
}

function countSelected(strategies: PaperStrategySnapshot[]) {
  return strategies.reduce((total, strategy) => total + (strategy.selected?.length || 0), 0);
}

function countRiskBlocks(strategies: PaperStrategySnapshot[], execution?: PaperStrategyPayload["paper_execution"]) {
  const strategyBlocks = strategies.reduce((total, strategy) => total + (strategy.risk_blocks?.length || 0), 0);
  return strategyBlocks + (execution?.runtime_gate_blocks?.length || 0);
}

function formatRegime(strategy: PaperStrategySnapshot) {
  const regime = strategy.regime || {};
  if (typeof regime.risk_on === "boolean") {
    return regime.risk_on ? "Risk on" : "Risk off";
  }
  const entries = Object.entries(regime).slice(0, 2);
  return entries.length ? entries.map(([key, value]) => `${formatName(key)}: ${String(value)}`).join(", ") : "unknown";
}

function formatSelected(strategy: PaperStrategySnapshot) {
  const selected = strategy.selected || [];
  if (!selected.length) {
    return "none";
  }
  return selected.map((item) => `${item.symbol} ${formatPercent(item.target_weight)}`).join(", ");
}

function formatOrders(strategy: PaperStrategySnapshot) {
  const orders = strategy.orders || [];
  if (!orders.length) {
    return "none";
  }
  return orders
    .slice(0, 3)
    .map((order) => {
      const notional = order.notional === null ? undefined : order.notional;
      return `${order.side.toUpperCase()} ${order.symbol}${notional ? ` ${formatCurrency(notional)}` : ""}${order.risk_approved ? " approved" : ""}`;
    })
    .join(", ");
}

function formatBlocks(blocks?: string[], warnings?: string[]) {
  const values = [...(blocks || []), ...(warnings || [])];
  return values.length ? values.map(formatName).join(", ") : "none";
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return `${(value * 100).toFixed(1)}%`;
}
