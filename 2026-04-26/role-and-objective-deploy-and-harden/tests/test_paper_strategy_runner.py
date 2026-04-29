from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.config import build_settings
from trading_system.trading import paper_strategy_runner


class FakeProvider:
    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        return {symbol: bars_from_prices(symbol, trend_prices(drift=0.2)) for symbol in symbols}

    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, dict[str, float]]:
        return default_quotes(symbols)

    def fetch_crypto_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        return {symbol: bars_from_prices(symbol, trend_prices(drift=1.0, base=1_000.0)) for symbol in symbols}


def settings(tmpdir: str) -> object:
    return build_settings(
        {
            "APP_ENV": "paper",
            "TRADING_MODE": "paper",
            "LIVE_TRADING_ENABLED": "false",
            "HOST": "127.0.0.1",
            "POSTGRES_URL": "postgresql://trader_app:test@127.0.0.1:5432/trading_system_paper",
            "REDIS_URL": "redis://127.0.0.1:6379/1",
            "ALPACA_API_KEY": "paper",
            "ALPACA_API_SECRET": "paper",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
            "ALPACA_CLI_PROFILE": "paper",
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
            "MAX_ORDER_NOTIONAL_USD": "25",
            "MAX_POSITION_NOTIONAL_USD": "50",
            "MAX_DAILY_LOSS_USD": "25",
            "MAX_TOTAL_DRAWDOWN_USD": "100",
            "MAX_ACCOUNT_RISK_PCT": "1.0",
            "REQUIRE_LIMIT_ORDERS": "true",
            "HEALTH_CHECKS_ENABLED": "true",
        }
    )


class PaperStrategyRunnerTests(unittest.TestCase):
    def test_run_once_writes_status_without_live_trading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            with patch.object(paper_strategy_runner, "_provider", return_value=FakeProvider()):
                payload = paper_strategy_runner.run_once(settings(tmpdir))
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["live_trading_changed"])
            self.assertEqual(payload["mode"], "paper")
            self.assertEqual(payload["paper_execution"]["status"], "disabled")
            self.assertTrue(Path(tmpdir, "state", "paper_strategy_status.json").exists())
            self.assertTrue(Path(tmpdir, "logs", "paper_strategy_rebalances.jsonl").exists())

    def test_run_once_can_submit_small_paper_entry_orders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            captured: list[tuple[list[str], dict[str, str]]] = []

            paper_settings = settings(tmpdir)
            paper_settings.raw["PAPER_ENTRY_EXECUTION_ENABLED"] = "true"
            paper_settings.raw["PAPER_ENTRY_NOTIONAL_USD"] = "1.00"
            paper_settings.raw["PAPER_ENTRY_ORDER_TYPE"] = "limit"
            paper_settings.raw["ALPACA_CONFIG_DIR"] = str(Path(tmpdir) / "alpaca")

            def fake_run(command: list[str], **kwargs: object) -> object:
                captured.append((command, dict(kwargs.get("env") or {})))
                return SimpleNamespace(returncode=0, stdout='{"id":"paper-order"}', stderr="")

            with (
                patch.dict(os.environ, {"ALPACA_SECRET_KEY": "must-not-leak"}),
                patch.object(paper_strategy_runner, "_provider", return_value=FakeProvider()),
                patch.object(paper_strategy_runner, "_market_clock", return_value={"is_open": True}),
                patch.object(paper_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = paper_strategy_runner.run_once(paper_settings)

            execution = payload["paper_execution"]
            self.assertEqual(execution["status"], "complete")
            self.assertGreaterEqual(len(execution["orders"]), 1)
            self.assertTrue(any(order["submitted"] for order in execution["orders"]))
            first_command, first_env = captured[0]
            self.assertEqual(first_command[:3], ["alpaca", "order", "submit"])
            self.assertIn("--client-order-id", first_command)
            client_order_id = first_command[first_command.index("--client-order-id") + 1]
            self.assertLessEqual(len(client_order_id), 48)
            self.assertTrue(client_order_id.startswith("etrv1-"))
            self.assertIn("--type", first_command)
            self.assertIn("limit", first_command)
            self.assertEqual(first_env["ALPACA_PROFILE"], "paper")
            self.assertEqual(first_env["ALPACA_LIVE_TRADE"], "false")
            self.assertNotIn("ALPACA_SECRET_KEY", first_env)
            self.assertTrue(Path(tmpdir, "state", "paper_entry_orders.json").exists())

    def test_enabled_paper_entries_wait_when_market_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            paper_settings = settings(tmpdir)
            paper_settings.raw["PAPER_ENTRY_EXECUTION_ENABLED"] = "true"
            with (
                patch.object(paper_strategy_runner, "_provider", return_value=FakeProvider()),
                patch.object(paper_strategy_runner, "_market_clock", return_value={"is_open": False}),
                patch.object(paper_strategy_runner.subprocess, "run") as broker_call,
            ):
                payload = paper_strategy_runner.run_once(paper_settings)

            self.assertEqual(payload["paper_execution"]["status"], "blocked_market_closed")
            broker_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
