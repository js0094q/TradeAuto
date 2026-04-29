from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trading_system.broker.alpaca_sdk import AlpacaBroker
from trading_system.config import Settings, validate_settings
from trading_system.kill_switch import KillSwitch
from trading_system.storage.events import logs_are_writable
from trading_system.strategy.registry import default_registry


STARTED_AT = time.time()


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def health_payload() -> dict[str, Any]:
    return {"ok": True, "service": "trading-system", "uptime_seconds": round(time.time() - STARTED_AT, 3)}


def readiness_checks(settings: Settings, *, external: bool = True) -> list[Check]:
    checks: list[Check] = []
    validation = validate_settings(settings, mode=settings.trading_mode)
    checks.append(Check("startup_validation", validation.ok, "; ".join(validation.errors) or "ok"))

    try:
        logs_are_writable(Path(settings.raw.get("LOG_DIR", "/opt/trading-system/shared/logs")))
        checks.append(Check("logs_writable", True, "ok"))
    except OSError as exc:
        checks.append(Check("logs_writable", False, str(exc)))

    try:
        KillSwitch(settings.kill_switch_file).is_enabled()
        checks.append(Check("kill_switch_readable", True, "ok"))
    except OSError as exc:
        checks.append(Check("kill_switch_readable", False, str(exc)))

    try:
        registry = default_registry()
        checks.append(Check("strategy_engine_loaded", bool(registry.names()), ",".join(registry.names())))
    except Exception as exc:
        checks.append(Check("strategy_engine_loaded", False, str(exc)))

    checks.append(Check("risk_engine_loaded", True, "ok"))

    if external and settings.is_live:
        try:
            AlpacaBroker(settings).validate_connectivity()
            checks.append(Check("alpaca_sdk_connectivity", True, "ok"))
        except Exception as exc:
            checks.append(Check("alpaca_sdk_connectivity", False, str(exc)))
    elif external and settings.is_paper and settings.alpaca_cli_enabled:
        checks.append(Check("alpaca_sdk_connectivity", True, "skipped for paper CLI mode"))
    else:
        checks.append(Check("alpaca_sdk_connectivity", True, "skipped"))

    checks.append(
        Check(
            "telegram_configured",
            bool(settings.telegram_bot_token and settings.telegram_allowed_chat_ids),
            "ok" if settings.telegram_bot_token else "missing token or chat IDs",
        )
    )
    checks.append(Check("database_configured", bool(settings.postgres_url), "ok"))
    return checks


def readiness_payload(settings: Settings, *, external: bool = True) -> dict[str, Any]:
    checks = readiness_checks(settings, external=external)
    return {
        "ok": all(check.ok for check in checks),
        "checks": [check.__dict__ for check in checks],
    }


def metrics_payload(settings: Settings) -> dict[str, Any]:
    kill_switch_enabled = False
    try:
        kill_switch_enabled = KillSwitch(settings.kill_switch_file).is_enabled()
    except OSError:
        kill_switch_enabled = True
    return {
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "trading_mode": settings.trading_mode,
        "broker_account_status": "unknown",
        "market_open_status": "unknown",
        "data_freshness": "unknown",
        "open_positions": None,
        "open_orders": None,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "risk_rejects": None,
        "kill_switch_state": "enabled" if kill_switch_enabled else "disabled",
        "active_strategy": None,
        "strategy_score": None,
        "last_trade_time": None,
        "last_telegram_alert_time": None,
    }
