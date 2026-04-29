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


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("-", "/")
    if not normalized or "/" in normalized:
        return normalized
    for quote in ("USDT", "USDC", "USD"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            base = normalized[: -len(quote)]
            if base:
                return f"{base}/{quote}"
    return normalized


def _paper_positions_snapshot(settings: Settings) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
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
        avg_entry_price = _float_or_none(item.get("avg_entry_price"))
        positions[symbol] = {
            "symbol": symbol,
            "market_value": abs(market_value) if market_value is not None else None,
            "qty": abs(qty) if qty is not None else None,
            "avg_entry_price": avg_entry_price,
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


def _holding_bars_by_symbol(order_state: dict[str, Any], *, as_of: date) -> dict[str, int]:
    order_metadata = order_state.get("orders")
    if not isinstance(order_metadata, dict):
        return {}
    first_seen: dict[str, date] = {}
    for item in order_metadata.values():
        if not isinstance(item, dict):
            continue
        symbol = _normalize_symbol(str(item.get("symbol") or ""))
        submitted_at = item.get("submitted_at")
        if not symbol or not isinstance(submitted_at, str):
            continue
        try:
            submitted_date = datetime.fromisoformat(submitted_at.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        prior = first_seen.get(symbol)
        if prior is None or submitted_date < prior:
            first_seen[symbol] = submitted_date
    return {symbol: max((as_of - opened).days, 0) for symbol, opened in first_seen.items()}


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


def _limit_price_for(
    symbol: str,
    quotes: dict[str, object],
    *,
    side: str,
    buffer_bps: float,
    fallback: float | None = None,
) -> float | None:
    quote = quotes.get(symbol)
    ask = getattr(quote, "ask", None)
    bid = getattr(quote, "bid", None)
    if ask is None and isinstance(quote, dict):
        ask = quote.get("ask")
    if bid is None and isinstance(quote, dict):
        bid = quote.get("bid")
    try:
        ask_value = float(ask)
    except (TypeError, ValueError):
        ask_value = 0.0
    try:
        bid_value = float(bid)
    except (TypeError, ValueError):
        bid_value = 0.0

    value = ask_value
    if side == "sell":
        value = bid_value if bid_value > 0.0 else ask_value
    if value <= 0.0:
        value = float(fallback or 0.0)
    if value <= 0.0:
        return None
    buffer = max(buffer_bps, 0.0) / 10_000.0
    adjusted = value * (1.0 + buffer)
    if side == "sell":
        adjusted = value * (1.0 - buffer)
    if adjusted <= 0.0:
        return None
    return round(adjusted, 2)


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


def _strategy_mode(settings: Settings, key: str, *, default: str) -> str:
    value = str(settings.raw.get(key, default)).strip().lower()
    if value in {"paper", "paper_shadow", "shadow"}:
        return value
    return default


def _strategy_enabled(settings: Settings, key: str, *, default: bool) -> bool:
    raw = settings.raw.get(key)
    if raw is None:
        return default
    return parse_bool(raw)


def _execute_paper_entries(
    settings: Settings,
    *,
    shared: Path,
    selected_orders: tuple[OrderIntent, ...],
    quotes: dict[str, object],
    market_clock: dict[str, Any],
    positions_snapshot: dict[str, dict[str, float | str | None]] | None = None,
    position_lookup_error: str | None = None,
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
    positions = dict(positions_snapshot or {})
    if not positions and position_lookup_error is None:
        positions, position_lookup_error = _paper_positions_snapshot(settings)
    engine = RiskEngine(settings.risk)
    env = _paper_cli_env(settings)
    today = date.today().isoformat().replace("-", "")
    today_key = f"-{today}-"
    trades_today = sum(1 for order_id in seen if today_key in order_id)
    upsize_threshold = _paper_entry_upsize_threshold(settings)

    for intent in selected_orders:
        if intent.mode != "paper" or intent.side not in {"buy", "sell"}:
            continue
        asset_class = _asset_class_for_symbol(intent.symbol)
        suffix = "entry" if intent.side == "buy" else "exit"
        client_order_id = _client_order_id(intent.strategy_name, intent.symbol, today, suffix=suffix)
        entry: dict[str, Any] = {
            "symbol": intent.symbol,
            "side": intent.side,
            "client_order_id": client_order_id,
            "submitted": False,
        }
        target_notional = _paper_entry_notional(settings, intent, bankroll=bankroll, max_notional=max_notional)
        notional = target_notional
        if intent.side == "buy":
            entry["target_notional_usd"] = round(target_notional, 2)
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
        position = _position_for_symbol(positions, intent.symbol)
        current_notional = _float_or_none(position.get("market_value")) if isinstance(position, dict) else None
        current_qty = _float_or_none(position.get("qty")) if isinstance(position, dict) else None
        if current_notional is not None:
            entry["current_position_notional_usd"] = round(current_notional, 2)
        if current_qty is not None:
            entry["current_position_qty"] = round(current_qty, 6)

        if intent.side == "buy" and client_order_id in seen:
            stored_entry = order_metadata.get(client_order_id) if isinstance(order_metadata, dict) else None
            stored_notional = _float_or_none(stored_entry.get("notional_usd")) if isinstance(stored_entry, dict) else None
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

        if intent.side == "buy":
            if notional <= 0.0:
                entry["status"] = "blocked_non_positive_notional"
                payload["orders"].append(entry)
                continue
            quantity = max(notional / limit_price, 0.0)
        else:
            if client_order_id in seen:
                entry["status"] = "already_submitted"
                payload["orders"].append(entry)
                continue
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
                if intent.side == "sell":
                    for order_key, order_item in list(order_metadata.items()):
                        if isinstance(order_item, dict) and _normalize_symbol(str(order_item.get("symbol") or "")) == _normalize_symbol(intent.symbol):
                            order_metadata.pop(order_key, None)
                else:
                    order_metadata[client_order_id] = {
                        "symbol": intent.symbol,
                        "side": intent.side,
                        "notional_usd": round(notional, 2),
                        "target_notional_usd": round(target_notional, 2),
                        "submitted_at": datetime.now(UTC).isoformat(),
                    }
            if intent.side == "sell" and isinstance(position, dict):
                position["qty"] = 0.0
                position["market_value"] = 0.0
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
    default_strategy.config = replace(
        default_strategy.config,
        enabled=_strategy_enabled(settings, "PAPER_STRATEGY_PRIMARY_ENABLED", default=default_strategy.config.enabled),
    )
    overlay_strategy.config = replace(
        overlay_strategy.config,
        enabled=_strategy_enabled(settings, "PAPER_STRATEGY_OVERLAY_ENABLED", default=overlay_strategy.config.enabled),
    )
    reversion_strategy.config = replace(
        reversion_strategy.config,
        enabled=_strategy_enabled(settings, "PAPER_STRATEGY_REVERSION_ENABLED", default=reversion_strategy.config.enabled),
    )
    primary_mode = _strategy_mode(settings, "PAPER_STRATEGY_PRIMARY_MODE", default="paper")
    overlay_mode = _strategy_mode(settings, "PAPER_STRATEGY_OVERLAY_MODE", default="paper_shadow")
    reversion_mode = _strategy_mode(settings, "PAPER_STRATEGY_REVERSION_MODE", default="paper_shadow")
    universe = tuple(sorted(set(default_strategy.config.universe + overlay_strategy.config.universe + reversion_strategy.config.universe)))
    managed_universe = set(universe)
    order_state = _load_order_state(shared)
    positions_snapshot, position_lookup_error = _paper_positions_snapshot(settings)
    position_symbols = sorted(
        symbol
        for symbol, item in positions_snapshot.items()
        if symbol in managed_universe and (_float_or_none(item.get("qty")) or 0.0) > 0.0
    )
    holding_bars = _holding_bars_by_symbol(order_state, as_of=date.today())
    reversion_positions = {
        symbol: {
            "entry_price": _float_or_none(item.get("avg_entry_price")),
            "holding_bars": holding_bars.get(symbol, 0),
        }
        for symbol, item in positions_snapshot.items()
        if symbol in set(reversion_strategy.config.universe) and (_float_or_none(item.get("qty")) or 0.0) > 0.0
    }

    start = _lookback_start()
    end = _today()
    LOGGER.info("fetching paper strategy market data universe=%s start=%s end=%s", ",".join(universe), start, end)
    equity_bars = provider.fetch_bars(universe, "1Day", start, end)
    quotes = provider.fetch_latest_quote(universe)
    crypto_bars = provider.fetch_crypto_bars(("BTC/USD", "ETH/USD"), "1Day", start, end)

    default_rebalance = default_strategy.rebalance(
        bars_by_symbol=equity_bars,
        quotes_by_symbol=quotes,
        current_positions=tuple(position_symbols),
        mode=primary_mode,
        kill_switch_enabled=kill_switch_enabled,
        portfolio_value=_paper_entry_bankroll(settings),
    )
    overlay_rebalance = overlay_strategy.rebalance(
        bars_by_symbol=equity_bars,
        crypto_bars_by_symbol=crypto_bars,
        quotes_by_symbol=quotes,
        current_positions=tuple(position_symbols),
        mode=overlay_mode,
        kill_switch_enabled=kill_switch_enabled,
    )
    reversion_rebalance = reversion_strategy.rebalance(
        bars_by_symbol=equity_bars,
        quotes_by_symbol=quotes,
        positions_by_symbol=reversion_positions,
        mode=reversion_mode,
        kill_switch_enabled=kill_switch_enabled,
    )
    paper_execution = _execute_paper_entries(
        settings,
        shared=shared,
        selected_orders=default_rebalance.orders,
        quotes=quotes,
        market_clock=_market_clock(settings),
        positions_snapshot=positions_snapshot,
        position_lookup_error=position_lookup_error,
    )
    payload = {
        "ok": True,
        "mode": "paper",
        "live_trading_changed": False,
        "timestamp": datetime.now(UTC).isoformat(),
        "kill_switch_enabled": kill_switch_enabled,
        "position_lookup_error": position_lookup_error,
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
