from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.config import build_settings
from trading_system.trading import live_strategy_runner


class FakeProvider:
    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        drifts = {
            "SPY": 0.12,
            "QQQ": 0.42,
            "IWM": 0.18,
            "DIA": 0.10,
            "XLK": 0.50,
            "XLF": 0.08,
            "XLE": 0.05,
            "XLV": 0.11,
            "XLY": 0.34,
            "XLP": 0.07,
            "TLT": 0.03,
            "GLD": 0.09,
        }
        return {symbol: bars_from_prices(symbol, trend_prices(drift=drifts.get(symbol, 0.2))) for symbol in symbols}

    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, dict[str, float]]:
        return default_quotes(symbols)


def settings(tmpdir: str, overrides: dict[str, str] | None = None) -> object:
    values = {
        "APP_ENV": "live",
        "TRADING_MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "HOST": "127.0.0.1",
        "POSTGRES_URL": "postgresql://trader_app:test@127.0.0.1:5432/trading_system_live",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "ALPACA_API_KEY": "live-key",
        "ALPACA_API_SECRET": "live-secret",
        "ALPACA_BASE_URL": "https://api.alpaca.markets",
        "ALPACA_CLI_PROFILE": "live",
        "ALPACA_LIVE_TRADE": "true",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "123",
        "TELEGRAM_ADMIN_CHAT_IDS": "123",
        "JWT_SIGNING_KEY": "jwt",
        "ADMIN_TOKEN": "admin",
        "DASHBOARD_TOKEN": "dashboard",
        "LOG_DIR": str(Path(tmpdir) / "logs"),
        "KILL_SWITCH_FILE": str(Path(tmpdir) / "state" / "kill_switch.enabled"),
        "TRADING_SYSTEM_SHARED_DIR": tmpdir,
        "MAX_TRADES_PER_DAY": "3",
        "MAX_OPEN_POSITIONS": "3",
        "MAX_ORDER_NOTIONAL_USD": "100",
        "MAX_POSITION_NOTIONAL_USD": "100",
        "MAX_DAILY_LOSS_USD": "25",
        "MAX_TOTAL_DRAWDOWN_USD": "100",
        "MAX_ACCOUNT_RISK_PCT": "1.0",
        "REQUIRE_LIMIT_ORDERS": "true",
        "ALLOW_MARKET_ORDERS": "false",
        "HEALTH_CHECKS_ENABLED": "true",
    }
    if overrides:
        values.update(overrides)
    return build_settings(values)


class LiveStrategyRunnerTests(unittest.TestCase):
    def test_run_once_defaults_to_no_live_strategy_orders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            with patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run):
                payload = live_strategy_runner.run_once(settings(tmpdir))

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "live")
            self.assertEqual(payload["live_execution"]["status"], "blocked_by_runtime_gate")
            self.assertIn("live_strategy_execution_disabled", payload["live_execution"]["runtime_gate_blocks"])
            self.assertTrue(Path(tmpdir, "state", "live_strategy_status.json").exists())

    def test_execution_enabled_still_requires_confirmation_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            with patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run):
                payload = live_strategy_runner.run_once(
                    settings(tmpdir, {"LIVE_STRATEGY_EXECUTION_ENABLED": "true"})
                )

            self.assertEqual(payload["live_execution"]["status"], "blocked_by_runtime_gate")
            self.assertIn("live_strategy_confirmation_missing", payload["live_execution"]["runtime_gate_blocks"])

    def test_explicit_live_strategy_gate_submits_limit_orders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            captured: list[tuple[list[str], dict[str, str]]] = []

            def fake_run(command: list[str], **kwargs: object) -> object:
                captured.append((command, dict(kwargs.get("env") or {})))
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "position" in command:
                    return SimpleNamespace(returncode=0, stdout="[]", stderr="")
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                if "order" in command and "submit" in command:
                    return SimpleNamespace(returncode=0, stdout='{"id":"live-order"}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                    "ALPACA_CONFIG_DIR": str(Path(tmpdir) / "alpaca"),
                },
            )
            with (
                patch.dict(os.environ, {"ALPACA_LIVE_TRADE": "false"}),
                patch.object(live_strategy_runner, "_provider", return_value=FakeProvider()),
                patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = live_strategy_runner.run_once(live_settings)

            execution = payload["live_execution"]
            self.assertEqual(execution["status"], "complete")
            submitted = [order for order in execution["orders"] if order["submitted"]]
            self.assertTrue(submitted)
            submit_commands = [(command, env) for command, env in captured if "submit" in command]
            self.assertTrue(submit_commands)
            first_command, first_env = submit_commands[0]
            self.assertIn("--profile", first_command)
            self.assertIn("live", first_command)
            self.assertIn("--type", first_command)
            self.assertIn("limit", first_command)
            self.assertIn("--client-order-id", first_command)
            self.assertEqual(first_env["ALPACA_PROFILE"], "live")
            self.assertEqual(first_env["ALPACA_LIVE_TRADE"], "true")


if __name__ == "__main__":
    unittest.main()
