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
  paper_execution_status?: string;
  paper_runtime_gate_passed?: boolean | null;
  paper_runtime_gate_blocks?: string[];
  live_execution_status?: string;
  live_runtime_gate_passed?: boolean | null;
  live_runtime_gate_blocks?: string[];
  paper_order_status_counts?: Record<string, number>;
  live_order_status_counts?: Record<string, number>;
  api_process_running?: boolean;
  paper_engine_running?: boolean;
  live_engine_running?: boolean;
  telegram_bot_running?: boolean;
  latest_api_error?: string | null;
  latest_paper_error?: string | null;
  latest_live_error?: string | null;
  latest_telegram_warning?: string | null;
};

export type PaperStrategyExecution = {
  status?: string;
  enabled?: boolean;
  runtime_gate_passed?: boolean;
  runtime_gate_blocks?: string[];
  position_lookup_error?: string;
  market_open?: boolean;
  bankroll_usd?: number;
  max_notional_usd?: number;
  notional_usd?: number;
  account_equity?: number;
  buying_power?: number;
  confirmation_required?: string;
  limit_buffer_bps?: number;
  order_type?: string;
  orders?: Array<{
    symbol?: string;
    side?: string;
    status?: string;
    submitted?: boolean;
    client_order_id?: string;
    original_client_order_id?: string;
    risk_blocks?: string[];
    error?: string;
    limit_price?: number;
    qty?: number;
    notional_usd?: number;
    returncode?: number;
    target_notional_usd?: number;
    current_position_notional_usd?: number;
    current_position_qty?: number;
    upsize_from_notional_usd?: number;
    position_lookup_error?: string;
  }>;
};

export type PaperStrategySnapshot = {
  strategy_name: string;
  mode: string;
  timestamp?: string;
  regime?: Record<string, string | number | boolean | null>;
  selected?: Array<{
    symbol: string;
    target_weight?: number | null;
    reason?: string;
    indicators?: Record<string, unknown>;
  }>;
  exits?: Array<{
    symbol: string;
    reason: string;
  }>;
  risk_blocks?: string[];
  orders?: Array<{
    strategy_name?: string;
    symbol: string;
    side: string;
    target_weight?: number | null;
    quantity?: number | null;
    notional?: number | null;
    reason?: string;
    risk_approved?: boolean;
    risk_blocks?: string[];
    mode?: string;
  }>;
  warnings?: string[];
};

export type PaperStrategyPayload = {
  ok: boolean;
  status: "available" | "missing" | "invalid" | string;
  message?: string;
  mode?: string;
  timestamp?: string | null;
  file_updated_at?: string | null;
  live_trading_changed?: boolean;
  kill_switch_enabled?: boolean;
  position_lookup_error?: string | null;
  paper_execution?: PaperStrategyExecution | null;
  strategies?: PaperStrategySnapshot[];
};

export type LiveStrategyPayload = {
  ok: boolean;
  status: "available" | "missing" | "invalid" | string;
  message?: string;
  mode?: string;
  timestamp?: string | null;
  file_updated_at?: string | null;
  kill_switch_enabled?: boolean;
  live_execution?: PaperStrategyExecution | null;
  strategies?: PaperStrategySnapshot[];
};
