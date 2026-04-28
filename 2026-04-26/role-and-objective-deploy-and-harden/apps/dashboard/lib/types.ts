export type ProxyEnvelope<T = unknown> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
};

export type HealthPayload = {
  ok: boolean;
  service: string;
  uptime_seconds: number;
};

export type ReadinessPayload = {
  ok: boolean;
  checks: Array<{
    name: string;
    ok: boolean;
    detail: string;
  }>;
};

export type MetricsPayload = {
  uptime_seconds?: number;
  trading_mode?: string;
  broker_account_status?: string;
  market_open_status?: string;
  data_freshness?: string;
  open_positions?: number | null;
  open_orders?: number | null;
  realized_pnl?: number | null;
  unrealized_pnl?: number | null;
  risk_rejects?: number | null;
  kill_switch_state?: string;
  active_strategy?: string | null;
  strategy_score?: number | null;
  last_trade_time?: string | null;
  last_telegram_alert_time?: string | null;
};
