from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from trading_system.config import LIVE_BASE_URL, Settings, load_settings, parse_bool, validate_settings
from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError
from trading_system.kill_switch import KillSwitch
from trading_system.runtime_state import ensure_runtime_state
from trading_system.storage.events import append_jsonl
from trading_system.strategies.equity_etf_trend_regime import EquityEtfTrendRegimeV1
from trading_system.strategies.strategy_config import default_equity_etf_trend_regime_config
from trading_system.trading.order_intents import OrderIntent
from trading_system.trading.paper_strategy_runner import (
    _asset_class_for_symbol,
    _float_or_none,
    _limit_price_for,
    _lookback_start,
    _normalize_symbol,
    _positive_float,
    _today,
)
from trading_system.trading.risk import AccountState, ExecutionGateState, MarketState, RiskEngine, RiskState


LOGGER = logging.getLogger("trading_system.trading.live_strategy_runner")
LIVE_STRATEGY_CONFIRMATION = "ENABLE_LIVE_STRATEGY_ORDERS"
DEFAULT_LIVE_LIMIT_BUFFER_BPS = 10.0


def _shared_dir(settings: Settings) -> Path:
    value = settings.raw.get("TRADING_SYSTEM_SHARED_DIR", ".runtime/shared")
    return Path(value)


def _live_cli_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env["ALPACA_PROFILE"] = settings.alpaca_cli_profile or "live"
    env["ALPACA_LIVE_TRADE"] = "true"
    env["ALPACA_QUIET"] = "1"
    if settings.raw.get("ALPACA_CONFIG_DIR"):
        env["ALPACA_CONFIG_DIR"] = str(settings.raw["ALPACA_CONFIG_DIR"])
    return env


def _alpaca_command(settings: Settings, *args: str) -> list[str]:
    command = ["alpaca"]
    profile = settings.alpaca_cli_profile or "live"
    if profile:
        command.extend(["--profile", profile])
    command.extend(args)
    command.append("--quiet")
    return command


def _provider(settings: Settings) -> CachedMarketDataProvider:
    shared = _shared_dir(settings)
    profile = settings.alpaca_cli_profile or "live"
    return CachedMarketDataProvider(
        AlpacaDataProvider(runner=CliRunner(profile=profile), feed=settings.alpaca_data_feed),
        DataCache(shared / "data" / "live_strategy_market_cache", ttl_seconds=300),
    )


def _json_cli(settings: Settings, *args: str) -> tuple[Any | None, str | None]:
    try:
        result = subprocess.run(
            _alpaca_command(settings, *args),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=_live_cli_env(settings),
        )
    except OSError as exc:
        return None, f"alpaca CLI unavailable: {exc}"
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()[:500] or "alpaca CLI command failed"
    try:
        return json.loads(result.stdout or "{}"), None
    except json.JSONDecodeError as exc:
        return None, f"invalid alpaca payload: {exc}"


def _market_clock(settings: Settings) -> dict[str, Any]:
    payload, error = _json_cli(settings, "clock")
    if error:
        return {"is_open": False, "error": error}
    return payload if isinstance(payload, dict) else {"is_open": False, "error": "unexpected clock payload"}


def _account_snapshot(settings: Settings) -> tuple[dict[str, Any], str | None]:
    payload, error = _json_cli(settings, "account", "get")
    if error:
        return {}, error
    if not isinstance(payload, dict):
        return {}, "unexpected account payload"
    return payload, None


def _positions_snapshot(settings: Settings) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
    payload, error = _json_cli(settings, "position", "list")
    if error:
        return {}, error
    if not isinstance(payload, list):
        return {}, "unexpected position payload"

    positions: dict[str, dict[str, float | str | None]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = _normalize_symbol(str(item.get("symbol") or ""))
        if not symbol:
            continue
        market_value = _float_or_none(item.get("market_value"))
        if market_value is None:
            market_value = _float_or_none(item.get("cost_basis"))
        qty = _float_or_none(item.get("qty_available"))
        if qty is None:
            qty = _float_or_none(item.get("qty"))
        positions[symbol] = {
            "symbol": symbol,
            "market_value": abs(market_value) if market_value is not None else None,
            "qty": abs(qty) if qty is not None else None,
            "avg_entry_price": _float_or_none(item.get("avg_entry_price")),
        }
    return positions, None


def _position_for_symbol(
    positions: dict[str, dict[str, float | str | None]],
    symbol: str,
) -> dict[str, float | str | None] | None:
    normalized = _normalize_symbol(symbol)
    direct = positions.get(normalized)
    if direct is not None:
        return direct
    compact = normalized.replace("/", "")
    for key, value in positions.items():
        if key.replace("/", "") == compact:
            return value
    return None


def _runtime_gate(settings: Settings) -> tuple[bool, tuple[str, ...]]:
    blocks: list[str] = []
    if settings.trading_mode != "live":
        blocks.append("trading_mode_not_live")
    if not settings.live_trading_enabled:
        blocks.append("live_trading_disabled")
    if settings.alpaca_base_url != LIVE_BASE_URL:
        blocks.append("not_live_alpaca_endpoint")
    if settings.raw.get("ALPACA_LIVE_TRADE", "false").strip().lower() != "true":
        blocks.append("alpaca_live_trade_not_true")
    if (settings.alpaca_cli_profile or "live") != "live":
        blocks.append("alpaca_profile_not_live")
    if not parse_bool(settings.raw.get("LIVE_STRATEGY_EXECUTION_ENABLED", "false")):
        blocks.append("live_strategy_execution_disabled")
    if settings.raw.get("LIVE_STRATEGY_CONFIRMATION", "") != LIVE_STRATEGY_CONFIRMATION:
        blocks.append("live_strategy_confirmation_missing")
    if settings.risk.allow_market_orders:
        blocks.append("market_orders_must_be_disabled_for_live_strategy")
    if not settings.risk.require_limit_orders:
        blocks.append("limit_orders_must_be_required_for_live_strategy")
    return not blocks, tuple(blocks)


def _state_path(shared: Path) -> Path:
    return shared / "state" / "live_strategy_orders.json"


def _status_path(shared: Path) -> Path:
    return shared / "state" / "live_strategy_status.json"


def _live_client_order_id(strategy_name: str, symbol: str, trade_date: str, *, suffix: str = "entry") -> str:
    strategy_prefixes = {"equity_etf_trend_regime_v1": "etrv1"}
    prefix = strategy_prefixes.get(strategy_name, strategy_name.replace("_", "-")[:12])
    clean_suffix = suffix.replace("_", "-")[:12]
    return f"{prefix}-{trade_date}-{symbol}-live-{clean_suffix}"[:48]


def _load_order_state(shared: Path) -> dict[str, Any]:
    path = _state_path(shared)
    if not path.exists():
        return {"client_order_ids": [], "orders": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"client_order_ids": [], "orders": {}}
    return payload if isinstance(payload, dict) else {"client_order_ids": [], "orders": {}}


def _write_order_state(shared: Path, payload: dict[str, Any]) -> None:
    path = _state_path(shared)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _limit_buffer_bps(settings: Settings) -> float:
    return _positive_float(
        settings.raw.get("LIVE_ENTRY_LIMIT_BUFFER_BPS"),
        default=DEFAULT_LIVE_LIMIT_BUFFER_BPS,
    )


def _live_order_notional(
    settings: Settings,
    intent: OrderIntent,
    *,
    account_equity: float,
    remaining_buying_power: float,
) -> float:
    fixed_notional = settings.raw.get("LIVE_ENTRY_NOTIONAL_USD")
    if fixed_notional not in (None, ""):
        target = _positive_float(fixed_notional, default=0.0)
    elif intent.notional and intent.notional > 0.0:
        target = intent.notional
    else:
        target = account_equity * max(intent.target_weight, 0.0)
    max_order = settings.risk.max_order_notional_usd or target
    return min(max(target, 0.0), max_order, max(remaining_buying_power, 0.0))


def _execute_live_orders(
    settings: Settings,
    *,
    shared: Path,
    selected_orders: tuple[OrderIntent, ...],
    quotes: dict[str, object],
    market_clock: dict[str, Any],
    account: dict[str, Any],
    positions_snapshot: dict[str, dict[str, float | str | None]],
    position_lookup_error: str | None,
    kill_switch_enabled: bool,
) -> dict[str, Any]:
    gate_ok, gate_blocks = _runtime_gate(settings)
    market_open = bool(market_clock.get("is_open", False))
    order_type = str(settings.raw.get("LIVE_ENTRY_ORDER_TYPE", "limit")).strip().lower()
    account_equity = _float_or_none(account.get("equity")) or 0.0
    buying_power = _float_or_none(account.get("buying_power")) or 0.0
    limit_buffer_bps = _limit_buffer_bps(settings)
    payload: dict[str, Any] = {
        "enabled": parse_bool(settings.raw.get("LIVE_STRATEGY_EXECUTION_ENABLED", "false")),
        "confirmation_required": LIVE_STRATEGY_CONFIRMATION,
        "runtime_gate_passed": gate_ok,
        "runtime_gate_blocks": list(gate_blocks),
        "market_open": market_open,
        "market_clock": market_clock,
        "account_equity": account_equity,
        "buying_power": buying_power,
        "order_type": order_type,
        "limit_buffer_bps": limit_buffer_bps,
        "orders": [],
    }
    if not gate_ok:
        payload["status"] = "blocked_by_runtime_gate"
        return payload
    if order_type != "limit":
        payload["status"] = "blocked_unsupported_order_type"
        payload["runtime_gate_blocks"].append("live_entry_order_type_must_be_limit")
        return payload
    if not selected_orders:
        payload["status"] = "no_entries"
        return payload

    state = _load_order_state(shared)
    seen = set(str(item) for item in state.get("client_order_ids", []))
    submitted_ids: list[str] = list(seen)
    order_metadata = state.get("orders") if isinstance(state.get("orders"), dict) else {}
    today = date.today().isoformat().replace("-", "")
    today_key = f"-{today}-"
    trades_today = sum(1 for order_id in seen if today_key in order_id)
    remaining_buying_power = buying_power
    open_positions = sum(1 for item in positions_snapshot.values() if (_float_or_none(item.get("qty")) or 0.0) > 0.0)
    engine = RiskEngine(settings.risk)
    env = _live_cli_env(settings)

    for intent in selected_orders:
        if intent.mode != "live" or intent.side not in {"buy", "sell"}:
            continue
        asset_class = _asset_class_for_symbol(intent.symbol)
        suffix = "entry" if intent.side == "buy" else "exit"
        client_order_id = _live_client_order_id(intent.strategy_name, intent.symbol, today, suffix=suffix)
        entry: dict[str, Any] = {
            "symbol": intent.symbol,
            "side": intent.side,
            "client_order_id": client_order_id,
            "submitted": False,
        }
        if not market_open and asset_class != "crypto":
            entry["status"] = "blocked_market_closed"
            payload["orders"].append(entry)
            continue
        limit_price = _limit_price_for(intent.symbol, quotes, side=intent.side, buffer_bps=limit_buffer_bps)
        if limit_price is None:
            entry["status"] = "blocked_missing_quote"
            payload["orders"].append(entry)
            continue
        entry["limit_price"] = limit_price
        if position_lookup_error:
            entry["position_lookup_error"] = position_lookup_error
        position = _position_for_symbol(positions_snapshot, intent.symbol)
        current_qty = _float_or_none(position.get("qty")) if isinstance(position, dict) else None
        current_notional = _float_or_none(position.get("market_value")) if isinstance(position, dict) else None
        if current_qty is not None:
            entry["current_position_qty"] = round(current_qty, 6)
        if current_notional is not None:
            entry["current_position_notional_usd"] = round(current_notional, 2)
        if client_order_id in seen:
            entry["status"] = "already_submitted"
            payload["orders"].append(entry)
            continue

        if intent.side == "buy":
            notional = _live_order_notional(
                settings,
                intent,
                account_equity=account_equity,
                remaining_buying_power=remaining_buying_power,
            )
            quantity = max(notional / limit_price, 0.0)
        else:
            if current_qty is None or current_qty <= 0.0:
                entry["status"] = "blocked_no_position"
                payload["orders"].append(entry)
                continue
            quantity = current_qty
            notional = round(abs(quantity * limit_price), 2)

        sized_intent = replace(intent, quantity=quantity, notional=notional)
        approved = engine.evaluate_intent(
            sized_intent.with_risk_decision(approved=False, blocks=()),
            AccountState(
                buying_power=remaining_buying_power if intent.side == "buy" else buying_power,
                market_is_open=market_open or asset_class == "crypto",
                open_positions=open_positions,
                trades_today=trades_today,
            ),
            MarketState(asset_tradable=True, spread_pct=0.01),
            RiskState(kill_switch_enabled=kill_switch_enabled),
            execution=ExecutionGateState(
                profile="live",
                enable_live_trading=settings.live_trading_enabled,
                allow_live_orders=True,
                broker_account_valid=True,
                strategy_live_enabled=True,
            ),
            order_type=order_type,
            limit_price=limit_price,
            asset_class=asset_class,
        )
        entry["risk_blocks"] = list(approved.risk_blocks)
        if not approved.risk_approved:
            entry["status"] = "blocked_by_risk_engine"
            payload["orders"].append(entry)
            continue

        command = _alpaca_command(
            settings,
            "order",
            "submit",
            "--symbol",
            intent.symbol,
            "--side",
            intent.side,
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
        )
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30, env=env)
        except OSError as exc:
            entry["status"] = "submit_failed"
            entry["error"] = f"alpaca CLI unavailable: {exc}"[:500]
            payload["orders"].append(entry)
            continue
        entry["qty"] = round(quantity, 6)
        entry["notional_usd"] = round(notional, 2)
        entry["returncode"] = result.returncode
        if result.returncode == 0:
            entry["submitted"] = True
            entry["status"] = "submitted"
            submitted_ids.append(client_order_id)
            trades_today += 1
            if intent.side == "buy":
                remaining_buying_power = max(remaining_buying_power - notional, 0.0)
                open_positions += 1
            if isinstance(order_metadata, dict):
                order_metadata[client_order_id] = {
                    "symbol": intent.symbol,
                    "side": intent.side,
                    "notional_usd": round(notional, 2),
                    "submitted_at": datetime.now(UTC).isoformat(),
                }
        else:
            entry["status"] = "submit_failed"
            entry["error"] = (result.stderr or result.stdout).strip()[:500]
        payload["orders"].append(entry)

    state["client_order_ids"] = sorted(set(submitted_ids))
    if isinstance(order_metadata, dict):
        state["orders"] = order_metadata
    state["updated_at"] = datetime.now(UTC).isoformat()
    _write_order_state(shared, state)
    if payload["orders"] and all(order.get("status") == "blocked_market_closed" for order in payload["orders"]):
        payload["status"] = "blocked_market_closed"
    else:
        payload["status"] = "complete"
    return payload


def _write_status(shared: Path, payload: dict[str, Any]) -> None:
    status_path = _status_path(shared)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _load_status(shared: Path) -> dict[str, Any]:
    path = _status_path(shared)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_trade_date(payload: dict[str, Any]) -> date | None:
    timestamp = payload.get("timestamp") or payload.get("file_updated_at")
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC).date() if parsed.tzinfo else parsed.date()


def _last_same_day_exit_intents(
    previous_status: dict[str, Any],
    *,
    position_symbols: tuple[str, ...],
) -> tuple[OrderIntent, ...]:
    if _payload_trade_date(previous_status) != datetime.now(UTC).date():
        return ()
    position_set = {_normalize_symbol(symbol) for symbol in position_symbols}
    strategies = previous_status.get("strategies")
    if not isinstance(strategies, list):
        return ()

    intents: list[OrderIntent] = []
    seen: set[str] = set()
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        orders = strategy.get("orders")
        if not isinstance(orders, list):
            continue
        for order in orders:
            if not isinstance(order, dict) or order.get("side") != "sell":
                continue
            symbol = _normalize_symbol(str(order.get("symbol") or ""))
            if not symbol or symbol not in position_set or symbol in seen:
                continue
            intents.append(
                OrderIntent(
                    strategy_name=str(order.get("strategy_name") or strategy.get("strategy_name") or "live_exit_fallback"),
                    symbol=symbol,
                    side="sell",
                    target_weight=0.0,
                    quantity=None,
                    notional=None,
                    reason=str(order.get("reason") or "last_same_day_exit_intent"),
                    mode="live",
                )
            )
            seen.add(symbol)
    return tuple(intents)


def _market_data_error_text(exc: MarketDataProviderError) -> str:
    return str(exc)[:500]


def _gate_only_payload(settings: Settings, *, kill_switch_enabled: bool) -> dict[str, Any]:
    shared = _shared_dir(settings)
    account, account_error = _account_snapshot(settings)
    market_clock = _market_clock(settings)
    execution = _execute_live_orders(
        settings,
        shared=shared,
        selected_orders=(),
        quotes={},
        market_clock=market_clock,
        account=account,
        positions_snapshot={},
        position_lookup_error=None,
        kill_switch_enabled=kill_switch_enabled,
    )
    if account_error:
        execution["account_error"] = account_error
    return {
        "ok": True,
        "mode": "live",
        "timestamp": datetime.now(UTC).isoformat(),
        "kill_switch_enabled": kill_switch_enabled,
        "live_execution": execution,
        "strategies": [],
    }


def run_once(settings: Settings) -> dict[str, Any]:
    validation = validate_settings(settings, mode="live")
    if not validation.ok:
        raise RuntimeError("live validation failed: " + "; ".join(validation.errors))

    shared = _shared_dir(settings)
    ensure_runtime_state(
        shared_dir=shared,
        log_dir=Path(settings.raw.get("LOG_DIR", str(shared / "logs"))),
        kill_switch_file=settings.kill_switch_file,
        mode="live",
    )
    try:
        kill_switch_enabled = KillSwitch(settings.kill_switch_file).is_enabled()
    except OSError as exc:
        LOGGER.warning("kill switch unreadable; treating as enabled: %s", exc)
        kill_switch_enabled = True

    gate_ok, _gate_blocks = _runtime_gate(settings)
    if not gate_ok:
        payload = _gate_only_payload(settings, kill_switch_enabled=kill_switch_enabled)
        append_jsonl(shared / "logs" / "live_strategy_rebalances.jsonl", payload)
        _write_status(shared, payload)
        return payload

    account, account_error = _account_snapshot(settings)
    if account_error:
        raise RuntimeError("live account lookup failed: " + account_error)
    positions_snapshot, position_lookup_error = _positions_snapshot(settings)
    position_symbols = sorted(
        symbol
        for symbol, item in positions_snapshot.items()
        if (_float_or_none(item.get("qty")) or 0.0) > 0.0
    )

    base_config = default_equity_etf_trend_regime_config()
    strategy = EquityEtfTrendRegimeV1(
        replace(
            base_config,
            enabled=parse_bool(settings.raw.get("LIVE_STRATEGY_PRIMARY_ENABLED", "true")),
            mode="live",
            execution=replace(base_config.execution, allow_live_orders=True, order_type="limit"),
        )
    )
    universe = tuple(strategy.config.universe)
    provider = _provider(settings)
    start = _lookback_start()
    end = _today()
    LOGGER.info("fetching live strategy market data universe=%s start=%s end=%s", ",".join(universe), start, end)
    account_equity = _float_or_none(account.get("equity")) or 0.0
    previous_status = _load_status(shared)
    fallback_used = False
    market_data_error: str | None = None
    strategies: list[dict[str, Any]] = []
    try:
        equity_bars = provider.fetch_bars(universe, "1Day", start, end)
        quote_symbols = tuple(dict.fromkeys((*universe, *position_symbols)))
        quotes = provider.fetch_latest_quote(quote_symbols)
        rebalance = strategy.rebalance(
            bars_by_symbol=equity_bars,
            quotes_by_symbol=quotes,
            current_positions=tuple(position_symbols),
            mode="live",
            kill_switch_enabled=kill_switch_enabled,
            portfolio_value=account_equity,
        )
        selected_orders = rebalance.orders
        strategies = [rebalance.to_dashboard_payload()]
    except MarketDataProviderError as exc:
        market_data_error = _market_data_error_text(exc)
        LOGGER.error("market data unavailable: %s", exc)
        selected_orders = _last_same_day_exit_intents(previous_status, position_symbols=tuple(position_symbols))
        quote_symbols = tuple(dict.fromkeys(intent.symbol for intent in selected_orders))
        previous_strategies = previous_status.get("strategies")
        strategies = previous_strategies if isinstance(previous_strategies, list) else []
        fallback_used = bool(selected_orders)
        if fallback_used:
            quotes = provider.fetch_latest_quote(quote_symbols)
        else:
            quotes = {}
    live_execution = _execute_live_orders(
        settings,
        shared=shared,
        selected_orders=selected_orders,
        quotes=quotes,
        market_clock=_market_clock(settings),
        account=account,
        positions_snapshot=positions_snapshot,
        position_lookup_error=position_lookup_error,
        kill_switch_enabled=kill_switch_enabled,
    )
    if market_data_error:
        live_execution["market_data_error"] = market_data_error
        live_execution["exit_fallback_used"] = fallback_used
        if not fallback_used:
            live_execution["status"] = "blocked_market_data_unavailable"
    payload = {
        "ok": True,
        "mode": "live",
        "timestamp": datetime.now(UTC).isoformat(),
        "kill_switch_enabled": kill_switch_enabled,
        "live_execution": live_execution,
        "strategies": strategies,
    }
    append_jsonl(shared / "logs" / "live_strategy_rebalances.jsonl", payload)
    _write_status(shared, payload)
    LOGGER.info(
        "live strategy cycle complete selected=%s risk_blocks=%s live_execution=%s",
        ",".join(str(item.get("symbol")) for strategy_payload in strategies for item in strategy_payload.get("selected", []) if isinstance(item, dict)) or "none",
        ",".join(str(block) for strategy_payload in strategies for block in strategy_payload.get("risk_blocks", [])) or "none",
        live_execution.get("status"),
    )
    return payload


def run_loop(env_file: str | None, *, interval_seconds: int, run_once_only: bool = False) -> int:
    settings = load_settings(env_file)
    validation = validate_settings(settings, mode="live")
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
            LOGGER.exception("live strategy cycle failed")
        if run_once_only:
            break
        for _ in range(max(1, interval_seconds)):
            if not running:
                break
            time.sleep(1)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live-mode strategy rebalance diagnostics.")
    parser.add_argument("--env-file")
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return run_loop(args.env_file, interval_seconds=args.interval_seconds, run_once_only=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
