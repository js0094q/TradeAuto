from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.config import build_settings
from trading_system.trading.order_intents import OrderIntent
from trading_system.trading import paper_strategy_runner


class FakeProvider:
    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        return {symbol: bars_from_prices(symbol, trend_prices(drift=0.2)) for symbol in symbols}

    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, dict[str, float]]:
        return default_quotes(symbols)

    def fetch_crypto_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        return {symbol: bars_from_prices(symbol, trend_prices(drift=1.0, base=1_000.0)) for symbol in symbols}


def settings(tmpdir: str, overrides: dict[str, str] | None = None) -> object:
    values = {
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
    if overrides:
        values.update(overrides)
    return build_settings(values)


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

    def test_run_once_sizes_entries_from_paper_bankroll_when_fixed_notional_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            captured: list[list[str]] = []
            paper_settings = settings(
                tmpdir,
                overrides={
                    "PAPER_ENTRY_EXECUTION_ENABLED": "true",
                    "PAPER_ENTRY_BANKROLL_USD": "100000",
                    "PAPER_ENTRY_MAX_NOTIONAL_USD": "25000",
                    "PAPER_ENTRY_ORDER_TYPE": "limit",
                    "MAX_ORDER_NOTIONAL_USD": "25000",
                    "MAX_POSITION_NOTIONAL_USD": "30000",
                    "MAX_DAILY_LOSS_USD": "2500",
                    "MAX_TOTAL_DRAWDOWN_USD": "10000",
                },
            )

            def fake_run(command: list[str], **_kwargs: object) -> object:
                captured.append(command)
                return SimpleNamespace(returncode=0, stdout='{"id":"paper-order"}', stderr="")

            with (
                patch.object(paper_strategy_runner, "_provider", return_value=FakeProvider()),
                patch.object(paper_strategy_runner, "_market_clock", return_value={"is_open": True}),
                patch.object(paper_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = paper_strategy_runner.run_once(paper_settings)

            execution = payload["paper_execution"]
            self.assertEqual(execution["bankroll_usd"], 100000.0)
            self.assertEqual(execution["max_notional_usd"], 25000.0)
            submitted = [order for order in execution["orders"] if order["submitted"]]
            self.assertTrue(submitted)
            self.assertTrue(all(order["notional_usd"] == 25000.0 for order in submitted))
            qty_index = captured[0].index("--qty") + 1
            self.assertGreater(float(captured[0][qty_index]), 100.0)

    def test_duplicate_entry_can_be_upsized_when_existing_paper_position_is_tiny(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            paper_settings = settings(
                tmpdir,
                overrides={
                    "PAPER_ENTRY_EXECUTION_ENABLED": "true",
                    "PAPER_ENTRY_BANKROLL_USD": "100000",
                    "PAPER_ENTRY_MAX_NOTIONAL_USD": "25000",
                    "PAPER_ENTRY_ORDER_TYPE": "limit",
                    "MAX_TRADES_PER_DAY": "10",
                    "MAX_ORDER_NOTIONAL_USD": "25000",
                    "MAX_POSITION_NOTIONAL_USD": "30000",
                    "MAX_DAILY_LOSS_USD": "2500",
                    "MAX_TOTAL_DRAWDOWN_USD": "10000",
                },
            )
            intent = OrderIntent(
                strategy_name="equity_etf_trend_regime_v1",
                symbol="SPY",
                side="buy",
                target_weight=0.25,
                quantity=None,
                notional=None,
                reason="test",
                mode="paper",
            )
            today = paper_strategy_runner.date.today().isoformat().replace("-", "")
            original_id = paper_strategy_runner._client_order_id(intent.strategy_name, intent.symbol, today)
            Path(tmpdir, "state", "paper_entry_orders.json").write_text(
                f'{{"client_order_ids":["{original_id}"]}}\n',
                encoding="utf-8",
            )
            captured: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if command[:3] == ["alpaca", "position", "list"]:
                    return SimpleNamespace(
                        returncode=0,
                        stdout='[{"symbol":"SPY","market_value":"1.00"}]',
                        stderr="",
                    )
                captured.append(command)
                return SimpleNamespace(returncode=0, stdout='{"id":"paper-upsize"}', stderr="")

            with patch.object(paper_strategy_runner.subprocess, "run", side_effect=fake_run):
                execution = paper_strategy_runner._execute_paper_entries(
                    paper_settings,
                    shared=Path(tmpdir),
                    selected_orders=(intent,),
                    quotes={"SPY": {"ask": 100.0}},
                    market_clock={"is_open": True},
                )

            self.assertEqual(execution["status"], "complete")
            self.assertEqual(len(captured), 1)
            order = execution["orders"][0]
            self.assertEqual(order["status"], "submitted")
            self.assertEqual(order["current_position_notional_usd"], 1.0)
            self.assertEqual(order["notional_usd"], 24999.0)
            self.assertEqual(order["target_notional_usd"], 25000.0)
            client_order_id = captured[0][captured[0].index("--client-order-id") + 1]
            self.assertIn("up25000", client_order_id)
            qty = float(captured[0][captured[0].index("--qty") + 1])
            self.assertGreater(qty, 240.0)

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

    def test_crypto_entries_can_run_when_equity_market_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            paper_settings = settings(
                tmpdir,
                overrides={
                    "ALLOW_CRYPTO_TRADING": "true",
                    "PAPER_ENTRY_EXECUTION_ENABLED": "true",
                    "PAPER_ENTRY_NOTIONAL_USD": "1.00",
                    "PAPER_ENTRY_ORDER_TYPE": "limit",
                },
            )
            selected_orders = (
                OrderIntent(
                    strategy_name="crypto_trend_breakout_v1",
                    symbol="BTC/USD",
                    side="buy",
                    target_weight=0.25,
                    quantity=None,
                    notional=None,
                    reason="test",
                    mode="paper",
                ),
            )

            with patch.object(paper_strategy_runner.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as broker_call:
                execution = paper_strategy_runner._execute_paper_entries(
                    paper_settings,
                    shared=Path(tmpdir),
                    selected_orders=selected_orders,
                    quotes={"BTC/USD": {"ask": 100.0}},
                    market_clock={"is_open": False},
                )

            self.assertEqual(execution["status"], "complete")
            self.assertTrue(any(order["status"] == "submitted" for order in execution["orders"]))
            broker_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
