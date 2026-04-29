from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_system.config import PAPER_BASE_URL, Settings, load_settings, parse_bool, validate_settings
from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError
from trading_system.kill_switch import KillSwitch
from trading_system.storage.events import append_jsonl
from trading_system.strategies.cross_market_high_beta_confirmation import CrossMarketHighBetaConfirmationV1
from trading_system.strategies.equity_etf_trend_regime import EquityEtfTrendRegimeV1
from trading_system.strategies.liquid_etf_mean_reversion import LiquidEtfMeanReversionV1
from trading_system.trading.order_intents import OrderIntent
from trading_system.trading.risk import AccountState, ExecutionGateState, MarketState, RiskEngine, RiskState


LOGGER = logging.getLogger("trading_system.trading.paper_strategy_runner")
DEFAULT_PAPER_ENTRY_BANKROLL_USD = 100_000.0
DEFAULT_PAPER_ENTRY_MAX_NOTIONAL_USD = 25_000.0
DEFAULT_PAPER_ENTRY_UPSIZE_THRESHOLD_PCT = 0.95
DEFAULT_PAPER_ENTRY_LIMIT_BUFFER_BPS = 10.0


def _shared_dir(settings: Settings) -> Path:
    value = settings.raw.get("TRADING_SYSTEM_SHARED_DIR", "/opt/trading-system/shared")
    return Path(value)


def _lookback_start(days: int = 420) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _provider(settings: Settings) -> CachedMarketDataProvider:
    shared = _shared_dir(settings)
    profile = settings.alpaca_cli_profile or "paper"
    return CachedMarketDataProvider(
        AlpacaDataProvider(runner=CliRunner(profile=profile), feed=settings.alpaca_data_feed),
        DataCache(shared / "data" / "strategy_market_cache", ttl_seconds=3_600),
    )


def _paper_cli_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("ALPACA_SECRET_KEY", None)
    env["ALPACA_PROFILE"] = settings.alpaca_cli_profile or "paper"
    env["ALPACA_LIVE_TRADE"] = "false"
    env["ALPACA_QUIET"] = "1"
    if settings.raw.get("ALPACA_CONFIG_DIR"):
        env["ALPACA_CONFIG_DIR"] = str(settings.raw["ALPACA_CONFIG_DIR"])
    return env


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed


def _paper_position_market_values(settings: Settings) -> tuple[dict[str, float], str | None]:
    result = subprocess.run(
        ["alpaca", "position", "list", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=_paper_cli_env(settings),
    )
    if result.returncode != 0:
        return {}, (result.stderr or result.stdout).strip()[:500] or "alpaca position list failed"
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {}, f"invalid alpaca position payload: {exc}"
    if not isinstance(payload, list):
        return {}, "unexpected alpaca position payload"

    positions: dict[str, float] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue
        market_value = _float_or_none(item.get("market_value"))
        if market_value is None:
            market_value = _float_or_none(item.get("cost_basis"))
        if market_value is not None:
            positions[symbol] = abs(market_value)
    return positions, None


def _paper_runtime_gate(settings: Settings) -> tuple[bool, tuple[str, ...]]:
    blocks: list[str] = []
    if settings.trading_mode != "paper":
        blocks.append("trading_mode_not_paper")
    if settings.live_trading_enabled:
        blocks.append("live_trading_enabled")
    if settings.alpaca_base_url != PAPER_BASE_URL:
        blocks.append("not_paper_alpaca_endpoint")
    if settings.raw.get("ALPACA_LIVE_TRADE", "false").strip().lower() == "true":
        blocks.append("alpaca_live_trade_true")
    if (settings.alpaca_cli_profile or "paper") != "paper":
        blocks.append("alpaca_profile_not_paper")
    return not blocks, tuple(blocks)


def _market_clock(settings: Settings) -> dict[str, Any]:
    result = subprocess.run(
        ["alpaca", "clock", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=_paper_cli_env(settings),
    )
    if result.returncode != 0:
        return {"is_open": False, "error": result.stderr.strip() or result.stdout.strip() or "alpaca clock failed"}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"is_open": False, "error": f"invalid alpaca clock payload: {exc}"}
    if isinstance(payload, dict):
        return payload
    return {"is_open": False, "error": "unexpected alpaca clock payload"}


def _state_path(shared: Path) -> Path:
    return shared / "state" / "paper_entry_orders.json"


def _load_order_state(shared: Path) -> dict[str, Any]:
    path = _state_path(shared)
    if not path.exists():
        return {"client_order_ids": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"client_order_ids": []}
    return payload if isinstance(payload, dict) else {"client_order_ids": []}


def _write_order_state(shared: Path, payload: dict[str, Any]) -> None:
    path = _state_path(shared)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _limit_price_for(symbol: str, quotes: dict[str, object], *, buffer_bps: float, fallback: float | None = None) -> float | None:
    quote = quotes.get(symbol)
    ask = getattr(quote, "ask", None)
    if ask is None and isinstance(quote, dict):
        ask = quote.get("ask")
    try:
        value = float(ask)
    except (TypeError, ValueError):
        value = float(fallback or 0.0)
    if value <= 0.0:
        return None
    return round(value * (1.0 + max(buffer_bps, 0.0) / 10_000.0), 2)


def _client_order_id(strategy_name: str, symbol: str, trade_date: str, *, suffix: str = "entry") -> str:
    strategy_prefixes = {"equity_etf_trend_regime_v1": "etrv1"}
    prefix = strategy_prefixes.get(strategy_name, strategy_name.replace("_", "-")[:12])
    clean_suffix = suffix.replace("_", "-")[:12]
    return f"{prefix}-{trade_date}-{symbol}-paper-{clean_suffix}"[:48]


def _asset_class_for_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("-", "/")
    if "/" in normalized:
        _, quote = normalized.split("/", 1)
        if quote in {"USD", "USDT", "USDC"}:
            return "crypto"
    return "equity"


def _positive_float(value: str | None, *, default: float) -> float:
    try:
        parsed = float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0.0 else default


def _paper_entry_bankroll(settings: Settings) -> float:
    return _positive_float(
        settings.raw.get("PAPER_ENTRY_BANKROLL_USD"),
        default=DEFAULT_PAPER_ENTRY_BANKROLL_USD,
    )


def _paper_entry_max_notional(settings: Settings) -> float:
    configured = settings.raw.get("PAPER_ENTRY_MAX_NOTIONAL_USD")
    if configured not in (None, ""):
        return _positive_float(configured, default=DEFAULT_PAPER_ENTRY_MAX_NOTIONAL_USD)
    if settings.risk.max_order_notional_usd and settings.risk.max_order_notional_usd > 0:
        return settings.risk.max_order_notional_usd
    return DEFAULT_PAPER_ENTRY_MAX_NOTIONAL_USD


def _paper_entry_upsize_threshold(settings: Settings) -> float:
    threshold = _positive_float(
        settings.raw.get("PAPER_ENTRY_UPSIZE_THRESHOLD_PCT"),
        default=DEFAULT_PAPER_ENTRY_UPSIZE_THRESHOLD_PCT,
    )
    return min(max(threshold, 0.0), 1.0)


def _paper_entry_limit_buffer_bps(settings: Settings) -> float:
    return _positive_float(
        settings.raw.get("PAPER_ENTRY_LIMIT_BUFFER_BPS"),
        default=DEFAULT_PAPER_ENTRY_LIMIT_BUFFER_BPS,
    )


def _paper_entry_notional(settings: Settings, intent: OrderIntent, *, bankroll: float, max_notional: float) -> float:
    fixed_notional = settings.raw.get("PAPER_ENTRY_NOTIONAL_USD")
    if fixed_notional not in (None, ""):
        return min(_positive_float(fixed_notional, default=max_notional), max_notional)
    target_notional = intent.notional if intent.notional and intent.notional > 0.0 else bankroll * max(intent.target_weight, 0.0)
    return min(max(target_notional, 0.0), max_notional)


def _execute_paper_entries(
    settings: Settings,
    *,
    shared: Path,
    selected_orders: tuple[OrderIntent, ...],
    quotes: dict[str, object],
    market_clock: dict[str, Any],
) -> dict[str, Any]:
    enabled = parse_bool(settings.raw.get("PAPER_ENTRY_EXECUTION_ENABLED", "false"))
    gate_ok, gate_blocks = _paper_runtime_gate(settings)
    market_open = bool(market_clock.get("is_open", False))
    bankroll = _paper_entry_bankroll(settings)
    max_notional = _paper_entry_max_notional(settings)
    order_type = str(settings.raw.get("PAPER_ENTRY_ORDER_TYPE", "limit")).strip().lower()
    limit_buffer_bps = _paper_entry_limit_buffer_bps(settings)
    payload: dict[str, Any] = {
        "enabled": enabled,
        "runtime_gate_passed": gate_ok,
        "runtime_gate_blocks": list(gate_blocks),
        "market_open": market_open,
        "market_clock": market_clock,
        "bankroll_usd": bankroll,
        "max_notional_usd": max_notional,
        "notional_usd": max_notional,
        "order_type": order_type,
        "limit_buffer_bps": limit_buffer_bps,
        "orders": [],
    }
    if not enabled:
        payload["status"] = "disabled"
        return payload
    if not gate_ok:
        payload["status"] = "blocked_by_runtime_gate"
        return payload
    if not selected_orders:
        payload["status"] = "no_entries"
        return payload
    if order_type != "limit":
        payload["status"] = "blocked_unsupported_order_type"
        payload["runtime_gate_blocks"].append("paper_entry_order_type_must_be_limit")
        return payload

    state = _load_order_state(shared)
    seen = set(str(item) for item in state.get("client_order_ids", []))
    submitted_ids: list[str] = list(seen)
    order_metadata = state.get("orders") if isinstance(state.get("orders"), dict) else {}
    position_values: dict[str, float] | None = None
    position_lookup_error: str | None = None
    engine = RiskEngine(settings.risk)
    env = _paper_cli_env(settings)
    today = date.today().isoformat().replace("-", "")
    today_key = f"-{today}-"
    trades_today = sum(1 for order_id in seen if today_key in order_id)
    upsize_threshold = _paper_entry_upsize_threshold(settings)

    for intent in selected_orders:
        if intent.side != "buy" or intent.mode != "paper":
            continue
        asset_class = _asset_class_for_symbol(intent.symbol)
        client_order_id = _client_order_id(intent.strategy_name, intent.symbol, today)
        entry: dict[str, Any] = {
            "symbol": intent.symbol,
            "side": "buy",
            "client_order_id": client_order_id,
            "submitted": False,
        }
        target_notional = _paper_entry_notional(settings, intent, bankroll=bankroll, max_notional=max_notional)
        notional = target_notional
        entry["target_notional_usd"] = round(target_notional, 2)
        if not market_open and asset_class != "crypto":
            entry["status"] = "blocked_market_closed"
            payload["orders"].append(entry)
            continue
        limit_price = _limit_price_for(intent.symbol, quotes, buffer_bps=limit_buffer_bps)
        if limit_price is None:
            entry["status"] = "blocked_missing_quote"
            payload["orders"].append(entry)
            continue
        entry["limit_price"] = limit_price
        if client_order_id in seen:
            stored_entry = order_metadata.get(client_order_id) if isinstance(order_metadata, dict) else None
            stored_notional = _float_or_none(stored_entry.get("notional_usd")) if isinstance(stored_entry, dict) else None
            if position_values is None:
                position_values, position_lookup_error = _paper_position_market_values(settings)
            current_notional = position_values.get(intent.symbol.upper()) if position_values is not None else None
            if current_notional is not None:
                entry["current_position_notional_usd"] = round(current_notional, 2)
            if position_lookup_error:
                entry["position_lookup_error"] = position_lookup_error
            observed_notional = current_notional if current_notional is not None else stored_notional
            if observed_notional is None:
                entry["status"] = "already_submitted_position_unknown"
                payload["orders"].append(entry)
                continue
            if observed_notional >= target_notional * upsize_threshold:
                entry["notional_usd"] = round(observed_notional, 2)
                entry["status"] = "already_submitted"
                payload["orders"].append(entry)
                continue
            upsize_suffix = f"up{int(round(target_notional))}"
            upsize_client_order_id = _client_order_id(intent.strategy_name, intent.symbol, today, suffix=upsize_suffix)
            if upsize_client_order_id in seen:
                entry["client_order_id"] = upsize_client_order_id
                entry["original_client_order_id"] = client_order_id
                entry["status"] = "upsize_already_submitted"
                entry["notional_usd"] = round(max(target_notional - observed_notional, 0.0), 2)
                payload["orders"].append(entry)
                continue
            entry["original_client_order_id"] = client_order_id
            entry["client_order_id"] = upsize_client_order_id
            client_order_id = upsize_client_order_id
            notional = min(max(target_notional - observed_notional, 0.0), max_notional)
            entry["upsize_from_notional_usd"] = round(observed_notional, 2)
        if notional <= 0.0:
            entry["status"] = "blocked_non_positive_notional"
            payload["orders"].append(entry)
            continue
        quantity = max(notional / limit_price, 0.0)
        sized_intent = replace(intent, quantity=quantity, notional=notional)
        approved = engine.evaluate_intent(
            sized_intent.with_risk_decision(approved=False, blocks=()),
            AccountState(
                buying_power=1_000_000.0,
                market_is_open=market_open or asset_class == "crypto",
                trades_today=trades_today,
            ),
            MarketState(asset_tradable=True, spread_pct=0.01),
            RiskState(kill_switch_enabled=False),
            execution=ExecutionGateState(profile="paper"),
            order_type=order_type,
            limit_price=limit_price,
            asset_class=asset_class,
        )
        entry["risk_blocks"] = list(approved.risk_blocks)
        if not approved.risk_approved:
            entry["status"] = "blocked_by_risk_engine"
            payload["orders"].append(entry)
            continue

        command = [
            "alpaca",
            "order",
            "submit",
            "--symbol",
            intent.symbol,
            "--side",
            "buy",
            "--type",
            "limit",
            "--limit-price",
            f"{limit_price:.2f}",
            "--qty",
            f"{quantity:.6f}",
            "--time-in-force",
            "day",
            "--client-order-id",
            client_order_id,
            "--quiet",
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30, env=env)
        entry["qty"] = round(quantity, 6)
        entry["notional_usd"] = round(notional, 2)
        entry["returncode"] = result.returncode
        if result.returncode == 0:
            entry["submitted"] = True
            entry["status"] = "submitted"
            submitted_ids.append(client_order_id)
            trades_today += 1
            if isinstance(order_metadata, dict):
                order_metadata[client_order_id] = {
                    "symbol": intent.symbol,
                    "notional_usd": round(notional, 2),
                    "target_notional_usd": round(target_notional, 2),
                    "submitted_at": datetime.now(UTC).isoformat(),
                }
        else:
            entry["status"] = "submit_failed"
            entry["error"] = (result.stderr or result.stdout).strip()[:500]
        payload["orders"].append(entry)

    if payload["orders"] and all(order.get("status") == "blocked_market_closed" for order in payload["orders"]):
        payload["status"] = "blocked_market_closed"
        return payload

    state["client_order_ids"] = sorted(set(submitted_ids))
    if isinstance(order_metadata, dict):
        state["orders"] = order_metadata
    state["updated_at"] = datetime.now(UTC).isoformat()
    _write_order_state(shared, state)
    payload["status"] = "complete"
    return payload


def _write_status(shared: Path, payload: dict[str, Any]) -> None:
    status_path = shared / "state" / "paper_strategy_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def run_once(settings: Settings) -> dict[str, Any]:
    validation = validate_settings(settings, mode="paper")
    if not validation.ok:
        raise RuntimeError("paper validation failed: " + "; ".join(validation.errors))

    shared = _shared_dir(settings)
    shared.mkdir(parents=True, exist_ok=True)
    kill_switch_enabled = True
    try:
        kill_switch_enabled = KillSwitch(settings.kill_switch_file).is_enabled()
    except OSError as exc:
        LOGGER.warning("kill switch unreadable; treating as enabled: %s", exc)

    provider = _provider(settings)
    default_strategy = EquityEtfTrendRegimeV1()
    overlay_strategy = CrossMarketHighBetaConfirmationV1()
    reversion_strategy = LiquidEtfMeanReversionV1()
    universe = tuple(sorted(set(default_strategy.config.universe + overlay_strategy.config.universe + reversion_strategy.config.universe)))

    start = _lookback_start()
    end = _today()
    LOGGER.info("fetching paper strategy market data universe=%s start=%s end=%s", ",".join(universe), start, end)
    equity_bars = provider.fetch_bars(universe, "1Day", start, end)
    quotes = provider.fetch_latest_quote(universe)
    crypto_bars = provider.fetch_crypto_bars(("BTC/USD", "ETH/USD"), "1Day", start, end)

    default_rebalance = default_strategy.rebalance(
        bars_by_symbol=equity_bars,
        quotes_by_symbol=quotes,
        mode="paper",
        kill_switch_enabled=kill_switch_enabled,
        portfolio_value=_paper_entry_bankroll(settings),
    )
    overlay_rebalance = overlay_strategy.rebalance(
        bars_by_symbol=equity_bars,
        crypto_bars_by_symbol=crypto_bars,
        quotes_by_symbol=quotes,
        mode="paper_shadow",
        kill_switch_enabled=kill_switch_enabled,
    )
    reversion_rebalance = reversion_strategy.rebalance(
        bars_by_symbol=equity_bars,
        quotes_by_symbol=quotes,
        mode="paper_shadow",
        kill_switch_enabled=kill_switch_enabled,
    )
    paper_execution = _execute_paper_entries(
        settings,
        shared=shared,
        selected_orders=tuple(order for order in default_rebalance.orders if order.side == "buy"),
        quotes=quotes,
        market_clock=_market_clock(settings),
    )
    payload = {
        "ok": True,
        "mode": "paper",
        "live_trading_changed": False,
        "timestamp": datetime.now(UTC).isoformat(),
        "kill_switch_enabled": kill_switch_enabled,
        "paper_execution": paper_execution,
        "strategies": [
            default_rebalance.to_dashboard_payload(),
            overlay_rebalance.to_dashboard_payload(),
            reversion_rebalance.to_dashboard_payload(),
        ],
    }
    append_jsonl(shared / "logs" / "paper_strategy_rebalances.jsonl", payload)
    _write_status(shared, payload)
    LOGGER.info(
        "paper strategy cycle complete selected=%s risk_blocks=%s paper_execution=%s",
        ",".join(item.symbol for item in default_rebalance.selected) or "none",
        ",".join(default_rebalance.risk_blocks) or "none",
        paper_execution.get("status"),
    )
    return payload


def run_loop(env_file: str | None, *, interval_seconds: int, run_once_only: bool = False) -> int:
    settings = load_settings(env_file)
    validation = validate_settings(settings, mode="paper")
    if not validation.ok:
        LOGGER.error("startup validation failed: %s", "; ".join(validation.errors))
        return 2

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while running:
        try:
            run_once(settings)
        except MarketDataProviderError as exc:
            LOGGER.error("market data unavailable: %s", exc)
        except Exception:
            LOGGER.exception("paper strategy cycle failed")
        if run_once_only:
            break
        for _ in range(max(1, interval_seconds)):
            if not running:
                break
            time.sleep(1)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paper-mode strategy rebalance diagnostics.")
    parser.add_argument("--env-file")
    parser.add_argument("--interval-seconds", type=int, default=86_400)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return run_loop(args.env_file, interval_seconds=args.interval_seconds, run_once_only=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
