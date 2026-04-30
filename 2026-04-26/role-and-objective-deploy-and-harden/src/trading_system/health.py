from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_system.broker.alpaca_sdk import AlpacaBroker
from trading_system.config import Settings, validate_settings
from trading_system.kill_switch import KillSwitch
from trading_system.runtime_state import ensure_runtime_state
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

    shared = _shared_dir(settings)
    log_dir = Path(settings.raw.get("LOG_DIR", str(shared / "logs")))
    try:
        ensure_runtime_state(
            shared_dir=shared,
            log_dir=log_dir,
            kill_switch_file=settings.kill_switch_file,
            mode=settings.trading_mode or "paper",
        )
        checks.append(Check("runtime_state_bootstrap", True, "ok"))
    except OSError as exc:
        checks.append(Check("runtime_state_bootstrap", False, str(exc)))

    try:
        logs_are_writable(log_dir)
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
    shared = _shared_dir(settings)
    kill_switch_enabled = False
    try:
        kill_switch_enabled = KillSwitch(settings.kill_switch_file).is_enabled()
    except OSError:
        kill_switch_enabled = True
    process_states = _process_states()
    paper_order_state = _order_state(shared / "state" / "paper_entry_orders.json")
    live_order_state = _order_state(shared / "state" / "live_strategy_orders.json")
    paper_activity = _latest_paper_activity(shared / "logs" / "paper_strategy_rebalances.jsonl")
    live_activity = _latest_live_activity(shared / "logs" / "live_strategy_rebalances.jsonl")
    api_error = _latest_error_line(shared / "logs" / "api.err.log")
    paper_error = _latest_error_line(shared / "logs" / "paper.err.log")
    telegram_warning = _latest_warning_line(shared / "logs" / "telegram.err.log")
    paper_strategy = paper_strategy_status_payload(settings)
    paper_strategies = paper_strategy.get("strategies") if isinstance(paper_strategy.get("strategies"), list) else []
    active_strategy = None
    if paper_strategies:
        first_strategy = paper_strategies[0]
        if isinstance(first_strategy, dict):
            active_strategy = first_strategy.get("strategy_name")
    live_strategy = live_strategy_status_payload(settings)
    live_error = _suppress_stale_live_error(
        _latest_live_engine_error(shared / "logs" / "live.err.log"),
        live_strategy,
    )
    live_strategies = live_strategy.get("strategies") if isinstance(live_strategy.get("strategies"), list) else []
    if live_strategies:
        first_live_strategy = live_strategies[0]
        if isinstance(first_live_strategy, dict):
            active_strategy = first_live_strategy.get("strategy_name")
    paper_execution = paper_strategy.get("paper_execution")
    live_execution = live_strategy.get("live_execution")
    market_open_status = "unknown"
    execution_priority = (
        (live_execution, paper_execution) if settings.is_live else (paper_execution, live_execution)
    )
    for execution_item in execution_priority:
        if isinstance(execution_item, dict) and isinstance(execution_item.get("market_open"), bool):
            market_open_status = "open" if execution_item["market_open"] else "closed"
            break
    runtime_gate_blocks = ()
    if isinstance(paper_execution, dict):
        maybe_blocks = paper_execution.get("runtime_gate_blocks")
        if isinstance(maybe_blocks, list):
            runtime_gate_blocks = tuple(str(item) for item in maybe_blocks)
    live_runtime_gate_blocks = ()
    if isinstance(live_execution, dict):
        maybe_live_blocks = live_execution.get("runtime_gate_blocks")
        if isinstance(maybe_live_blocks, list):
            live_runtime_gate_blocks = tuple(str(item) for item in maybe_live_blocks)

    activity = live_activity if settings.is_live else paper_activity
    order_state = live_order_state if settings.is_live else paper_order_state

    return {
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "trading_mode": settings.trading_mode,
        "broker_account_status": (
            "live_engine_running"
            if process_states["live_engine_running"]
            else "paper_engine_running"
            if process_states["paper_engine_running"]
            else "unknown"
        ),
        "market_open_status": market_open_status,
        "data_freshness": str(
            (live_strategy if settings.is_live else paper_strategy).get("timestamp")
            or (live_strategy if settings.is_live else paper_strategy).get("file_updated_at")
            or "unknown"
        ),
        "open_positions": len(activity["latest_selected_symbols"]) or None,
        "open_orders": order_state.get("client_order_ids_count"),
        "realized_pnl": None,
        "unrealized_pnl": None,
        "risk_rejects": activity["latest_risk_rejects"] if activity["latest_risk_rejects"] else None,
        "kill_switch_state": "enabled" if kill_switch_enabled else "disabled",
        "active_strategy": active_strategy,
        "strategy_score": None,
        "last_trade_time": activity["last_submitted_trade_time"],
        "last_telegram_alert_time": telegram_warning,
        "latest_telegram_warning": telegram_warning,
        "paper_execution_status": paper_execution.get("status") if isinstance(paper_execution, dict) else "unknown",
        "paper_runtime_gate_passed": bool(paper_execution.get("runtime_gate_passed")) if isinstance(paper_execution, dict) else None,
        "paper_runtime_gate_blocks": list(runtime_gate_blocks),
        "live_execution_status": live_execution.get("status") if isinstance(live_execution, dict) else "unknown",
        "live_runtime_gate_passed": bool(live_execution.get("runtime_gate_passed")) if isinstance(live_execution, dict) else None,
        "live_runtime_gate_blocks": list(live_runtime_gate_blocks),
        "paper_order_status_counts": paper_activity["latest_order_status_counts"],
        "live_order_status_counts": live_activity["latest_order_status_counts"],
        "api_process_running": process_states["api_process_running"],
        "paper_engine_running": process_states["paper_engine_running"],
        "live_engine_running": process_states["live_engine_running"],
        "telegram_bot_running": process_states["telegram_bot_running"],
        "latest_api_error": api_error,
        "latest_paper_error": paper_error,
        "latest_live_error": live_error,
    }


def paper_strategy_status_payload(settings: Settings) -> dict[str, Any]:
    shared = _shared_dir(settings)
    log_dir = Path(settings.raw.get("LOG_DIR", str(shared / "logs")))
    bootstrap_error = None
    try:
        ensure_runtime_state(
            shared_dir=shared,
            log_dir=log_dir,
            kill_switch_file=settings.kill_switch_file,
            mode=settings.trading_mode or "paper",
        )
    except OSError as exc:
        bootstrap_error = str(exc)

    status_path = shared / "state" / "paper_strategy_status.json"
    if not status_path.exists():
        message = "paper strategy status has not been written yet"
        if bootstrap_error:
            message = f"{message}; runtime bootstrap failed: {bootstrap_error}"
        return {
            "ok": False,
            "status": "missing",
            "message": message,
            "mode": "paper",
            "strategies": [],
            "paper_execution": None,
        }

    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "message": f"paper strategy status is unreadable: {exc}",
            "mode": "paper",
            "strategies": [],
            "paper_execution": None,
        }

    if not isinstance(payload, dict):
        return {
            "ok": False,
            "status": "invalid",
            "message": "paper strategy status must be a JSON object",
            "mode": "paper",
            "strategies": [],
            "paper_execution": None,
        }

    strategies = payload.get("strategies")
    paper_execution = payload.get("paper_execution")
    try:
        file_updated_at = datetime.fromtimestamp(status_path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")
    except OSError:
        file_updated_at = None
    return {
        "ok": bool(payload.get("ok", False)),
        "status": "available",
        "mode": str(payload.get("mode") or "paper"),
        "timestamp": payload.get("timestamp"),
        "file_updated_at": file_updated_at,
        "live_trading_changed": bool(payload.get("live_trading_changed", False)),
        "kill_switch_enabled": bool(payload.get("kill_switch_enabled", False)),
        "paper_execution": paper_execution if isinstance(paper_execution, dict) else None,
        "strategies": strategies if isinstance(strategies, list) else [],
    }


def live_strategy_status_payload(settings: Settings) -> dict[str, Any]:
    shared = _shared_dir(settings)
    status_path = shared / "state" / "live_strategy_status.json"
    if not status_path.exists():
        return {
            "ok": False,
            "status": "missing",
            "message": "live strategy status has not been written yet",
            "mode": "live",
            "strategies": [],
            "live_execution": None,
        }

    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status": "invalid",
            "message": f"live strategy status is unreadable: {exc}",
            "mode": "live",
            "strategies": [],
            "live_execution": None,
        }

    if not isinstance(payload, dict):
        return {
            "ok": False,
            "status": "invalid",
            "message": "live strategy status must be a JSON object",
            "mode": "live",
            "strategies": [],
            "live_execution": None,
        }

    strategies = payload.get("strategies")
    live_execution = payload.get("live_execution")
    try:
        file_updated_at = datetime.fromtimestamp(status_path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")
    except OSError:
        file_updated_at = None
    return {
        "ok": bool(payload.get("ok", False)),
        "status": "available",
        "mode": str(payload.get("mode") or "live"),
        "timestamp": payload.get("timestamp"),
        "file_updated_at": file_updated_at,
        "kill_switch_enabled": bool(payload.get("kill_switch_enabled", False)),
        "live_execution": live_execution if isinstance(live_execution, dict) else None,
        "strategies": strategies if isinstance(strategies, list) else [],
    }


def _shared_dir(settings: Settings) -> Path:
    return Path(settings.raw.get("TRADING_SYSTEM_SHARED_DIR", ".runtime/shared"))


def _tail_lines(path: Path, *, max_lines: int = 300) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return [line.rstrip("\n") for line in deque(handle, maxlen=max_lines)]
    except OSError:
        return []


def _latest_error_line(path: Path) -> str | None:
    for line in reversed(_tail_lines(path)):
        if "ERROR" in line or "Traceback" in line:
            return line
    return None


def _latest_warning_line(path: Path) -> str | None:
    for line in reversed(_tail_lines(path)):
        if "WARNING" in line:
            return line
    return None


def _latest_live_engine_error(path: Path) -> str | None:
    lines = _tail_lines(path)
    if not lines:
        return None
    last_started_index = -1
    for index, line in enumerate(lines):
        if "trading engine started in live mode" in line:
            last_started_index = index
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if "ERROR" in line or "Traceback" in line:
            if last_started_index != -1 and index < last_started_index:
                return None
            return line
    return None


def _suppress_stale_live_error(error_line: str | None, live_strategy: dict[str, Any]) -> str | None:
    if not error_line:
        return None
    live_execution = live_strategy.get("live_execution")
    if not isinstance(live_execution, dict) or live_execution.get("status") != "complete":
        return error_line
    error_time = _log_line_timestamp(error_line)
    status_time = _payload_timestamp(live_strategy.get("timestamp") or live_strategy.get("file_updated_at"))
    if error_time is not None and status_time is not None and status_time > error_time:
        return None
    return error_line


def _log_line_timestamp(line: str) -> datetime | None:
    try:
        return datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f").replace(tzinfo=UTC)
    except ValueError:
        return None


def _payload_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _process_states() -> dict[str, bool]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "args="],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "api_process_running": False,
            "paper_engine_running": False,
            "live_engine_running": False,
            "telegram_bot_running": False,
        }

    lines = result.stdout.splitlines() if result.returncode == 0 else []
    return {
        "api_process_running": any("uvicorn trading_system.api.app:app" in line for line in lines),
        "paper_engine_running": any("trading_system.trading.paper_strategy_runner" in line for line in lines),
        "live_engine_running": any("trading_system.trading.engine --mode live" in line for line in lines),
        "telegram_bot_running": any("trading_system.telegram.bot" in line for line in lines),
    }


def _order_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"client_order_ids_count": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"client_order_ids_count": 0}
    if not isinstance(payload, dict):
        return {"client_order_ids_count": 0}
    client_ids = payload.get("client_order_ids")
    if not isinstance(client_ids, list):
        return {"client_order_ids_count": 0}
    return {"client_order_ids_count": len(client_ids)}


def _live_strategy_status(shared: Path) -> dict[str, Any]:
    path = shared / "state" / "live_strategy_status.json"
    if not path.exists():
        return {"live_execution": None, "strategies": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"live_execution": None, "strategies": []}
    return payload if isinstance(payload, dict) else {"live_execution": None, "strategies": []}


def _latest_paper_activity(path: Path) -> dict[str, Any]:
    return _latest_strategy_activity(path, execution_key="paper_execution")


def _latest_live_activity(path: Path) -> dict[str, Any]:
    return _latest_strategy_activity(path, execution_key="live_execution")


def _latest_strategy_activity(path: Path, *, execution_key: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "last_submitted_trade_time": None,
            "latest_risk_rejects": 0,
            "latest_selected_symbols": tuple(),
            "latest_order_status_counts": {},
        }

    last_submitted_trade_time = None
    latest_payload: dict[str, Any] | None = None

    for line in _tail_lines(path, max_lines=500):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        latest_payload = payload
        execution = payload.get(execution_key)
        if isinstance(execution, dict):
            for order in execution.get("orders") or []:
                if isinstance(order, dict) and order.get("status") == "submitted":
                    timestamp = payload.get("timestamp") or payload.get("ts")
                    if isinstance(timestamp, str):
                        last_submitted_trade_time = timestamp

    if latest_payload is None:
        return {
            "last_submitted_trade_time": None,
            "latest_risk_rejects": 0,
            "latest_selected_symbols": tuple(),
            "latest_order_status_counts": {},
        }

    latest_risk_rejects = 0
    latest_selected_symbols: list[str] = []
    latest_order_status_counts: Counter[str] = Counter()

    strategies = latest_payload.get("strategies")
    if isinstance(strategies, list):
        for index, strategy in enumerate(strategies):
            if not isinstance(strategy, dict):
                continue
            if index == 0:
                selected = strategy.get("selected")
                if isinstance(selected, list):
                    for item in selected:
                        if isinstance(item, dict):
                            symbol = item.get("symbol")
                            if isinstance(symbol, str):
                                latest_selected_symbols.append(symbol)
            risk_blocks = strategy.get("risk_blocks")
            if isinstance(risk_blocks, list):
                latest_risk_rejects += len(risk_blocks)

    execution = latest_payload.get(execution_key)
    if isinstance(execution, dict):
        for order in execution.get("orders") or []:
            if not isinstance(order, dict):
                continue
            status = str(order.get("status") or "unknown")
            latest_order_status_counts[status] += 1
            if status == "blocked_by_risk_engine":
                latest_risk_rejects += 1

    return {
        "last_submitted_trade_time": last_submitted_trade_time,
        "latest_risk_rejects": latest_risk_rejects,
        "latest_selected_symbols": tuple(latest_selected_symbols),
        "latest_order_status_counts": dict(latest_order_status_counts),
    }
