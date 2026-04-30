from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.config import build_settings
from trading_system.data.provider import MarketDataProviderError
from trading_system.trading.order_intents import OrderIntent
from trading_system.trading import live_strategy_runner


class FakeProvider:
    def __init__(self) -> None:
        self.latest_quote_symbols: tuple[str, ...] = ()

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
        self.latest_quote_symbols = symbols
        return default_quotes(symbols)


class FailingBarsProvider(FakeProvider):
    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        raise MarketDataProviderError("bars unavailable")


class FlakyBarsProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.fetch_bar_calls = 0

    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[object]]:
        self.fetch_bar_calls += 1
        if self.fetch_bar_calls == 1:
            raise MarketDataProviderError("connection reset by peer")
        return super().fetch_bars(symbols, timeframe, start, end)


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
            client_order_id = first_command[first_command.index("--client-order-id") + 1]
            self.assertIn("-live-entry", client_order_id)
            self.assertNotIn("-paper-", client_order_id)
            self.assertEqual(first_env["ALPACA_PROFILE"], "live")
            self.assertEqual(first_env["ALPACA_LIVE_TRADE"], "true")

    def test_live_strategy_submits_sell_for_deselected_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            captured: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "position" in command:
                    return SimpleNamespace(
                        returncode=0,
                        stdout='[{"symbol":"NEE","qty_available":"0.10447574","qty":"0.10447574","market_value":"25"}]',
                        stderr="",
                    )
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                if "order" in command and "submit" in command:
                    captured.append(command)
                    return SimpleNamespace(returncode=0, stdout='{"id":"live-order"}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                    "MAX_TRADES_PER_DAY": "10",
                },
            )
            provider = FakeProvider()
            with (
                patch.object(live_strategy_runner, "_provider", return_value=provider),
                patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = live_strategy_runner.run_once(live_settings)

            self.assertEqual(payload["live_execution"]["status"], "complete")
            self.assertIn("NEE", provider.latest_quote_symbols)
            sell_commands = [command for command in captured if "--side" in command and command[command.index("--side") + 1] == "sell"]
            self.assertTrue(sell_commands)
            sell = sell_commands[0]
            self.assertEqual(sell[sell.index("--symbol") + 1], "NEE")
            self.assertEqual(sell[sell.index("--qty") + 1], "0.104475")
            client_order_id = sell[sell.index("--client-order-id") + 1]
            self.assertIn("-live-exit", client_order_id)
            self.assertNotIn("-paper-", client_order_id)

    def test_live_buy_for_existing_position_does_not_hit_open_position_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            captured: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "order" in command and "submit" in command:
                    captured.append(command)
                    return SimpleNamespace(returncode=0, stdout='{"id":"live-order"}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                },
            )
            with patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run):
                execution = live_strategy_runner._execute_live_orders(
                    live_settings,
                    shared=Path(tmpdir),
                    selected_orders=(
                        OrderIntent(
                            strategy_name="equity_etf_trend_regime_v1",
                            symbol="XLE",
                            side="buy",
                            target_weight=0.25,
                            quantity=None,
                            notional=25.0,
                            reason="top_3_rank_and_regime_passed",
                            mode="live",
                        ),
                    ),
                    quotes={"XLE": {"bid": 59.00, "ask": 59.05}},
                    market_clock={"is_open": True},
                    account={"equity": "100", "buying_power": "100"},
                    positions_snapshot={
                        "XLE": {"symbol": "XLE", "qty": 0.429332, "market_value": 25.35},
                        "XLK": {"symbol": "XLK", "qty": 0.1567, "market_value": 24.64},
                        "QQQ": {"symbol": "QQQ", "qty": 0.0376, "market_value": 24.76},
                    },
                    position_lookup_error=None,
                    kill_switch_enabled=False,
                )

            self.assertEqual(execution["status"], "complete")
            self.assertEqual(execution["orders"][0]["status"], "submitted")
            self.assertNotIn("max open positions reached", execution["orders"][0]["risk_blocks"])
            self.assertTrue(captured)

    def test_live_buy_for_new_position_still_hits_open_position_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                },
            )
            execution = live_strategy_runner._execute_live_orders(
                live_settings,
                shared=Path(tmpdir),
                selected_orders=(
                    OrderIntent(
                        strategy_name="equity_etf_trend_regime_v1",
                        symbol="XLF",
                        side="buy",
                        target_weight=0.25,
                        quantity=None,
                        notional=25.0,
                        reason="top_3_rank_and_regime_passed",
                        mode="live",
                    ),
                ),
                quotes={"XLF": {"bid": 51.00, "ask": 51.05}},
                market_clock={"is_open": True},
                account={"equity": "100", "buying_power": "100"},
                positions_snapshot={
                    "XLE": {"symbol": "XLE", "qty": 0.429332, "market_value": 25.35},
                    "XLK": {"symbol": "XLK", "qty": 0.1567, "market_value": 24.64},
                    "QQQ": {"symbol": "QQQ", "qty": 0.0376, "market_value": 24.76},
                },
                position_lookup_error=None,
                kill_switch_enabled=False,
            )

            self.assertEqual(execution["orders"][0]["status"], "blocked_by_risk_engine")
            self.assertIn("max open positions reached", execution["orders"][0]["risk_blocks"])

    def test_live_strategy_uses_same_day_exit_fallback_when_bars_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir, "state")
            state_dir.mkdir()
            Path(tmpdir, "logs").mkdir()
            (state_dir / "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            previous_status = {
                "ok": True,
                "mode": "live",
                "timestamp": live_strategy_runner.datetime.now(live_strategy_runner.UTC).isoformat(),
                "live_execution": {"status": "complete"},
                "strategies": [
                    {
                        "strategy_name": "equity_etf_trend_regime_v1",
                        "mode": "live",
                        "selected": [{"symbol": "QQQ"}],
                        "risk_blocks": [],
                        "orders": [
                            {
                                "strategy_name": "equity_etf_trend_regime_v1",
                                "symbol": "NEE",
                                "side": "sell",
                                "target_weight": 0.0,
                                "reason": "deselected",
                                "mode": "live",
                            }
                        ],
                    }
                ],
            }
            (state_dir / "live_strategy_status.json").write_text(json.dumps(previous_status), encoding="utf-8")
            captured: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "position" in command:
                    return SimpleNamespace(
                        returncode=0,
                        stdout='[{"symbol":"NEE","qty":"0.5","market_value":"25"}]',
                        stderr="",
                    )
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                if "order" in command and "submit" in command:
                    captured.append(command)
                    return SimpleNamespace(returncode=0, stdout='{"id":"live-order"}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                    "LIVE_MARKET_DATA_MAX_ATTEMPTS": "1",
                    "MAX_TRADES_PER_DAY": "10",
                },
            )
            provider = FailingBarsProvider()
            with (
                patch.object(live_strategy_runner, "_provider", return_value=provider),
                patch.object(live_strategy_runner.LOGGER, "error"),
                patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = live_strategy_runner.run_once(live_settings)

            execution = payload["live_execution"]
            self.assertEqual(execution["status"], "complete")
            self.assertTrue(execution["exit_fallback_used"])
            self.assertIn("bars unavailable", execution["market_data_error"])
            self.assertEqual(provider.latest_quote_symbols, ("NEE",))
            sell_commands = [command for command in captured if "--side" in command and command[command.index("--side") + 1] == "sell"]
            self.assertTrue(sell_commands)
            self.assertEqual(sell_commands[0][sell_commands[0].index("--symbol") + 1], "NEE")

    def test_live_strategy_retries_transient_bar_failure_before_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "state").mkdir()
            Path(tmpdir, "state", "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            captured: list[list[str]] = []
            sleeps: list[float] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if "account" in command:
                    return SimpleNamespace(returncode=0, stdout='{"equity":"100","buying_power":"100"}', stderr="")
                if "position" in command:
                    return SimpleNamespace(returncode=0, stdout="[]", stderr="")
                if "clock" in command:
                    return SimpleNamespace(returncode=0, stdout='{"is_open":true}', stderr="")
                if "order" in command and "submit" in command:
                    captured.append(command)
                    return SimpleNamespace(returncode=0, stdout='{"id":"live-order"}', stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            live_settings = settings(
                tmpdir,
                {
                    "LIVE_STRATEGY_EXECUTION_ENABLED": "true",
                    "LIVE_STRATEGY_CONFIRMATION": live_strategy_runner.LIVE_STRATEGY_CONFIRMATION,
                    "MAX_TRADES_PER_DAY": "10",
                },
            )
            provider = FlakyBarsProvider()
            with (
                patch.object(live_strategy_runner, "_provider", return_value=provider),
                patch.object(live_strategy_runner.LOGGER, "warning") as warning,
                patch.object(live_strategy_runner.time, "sleep", side_effect=sleeps.append),
                patch.object(live_strategy_runner.subprocess, "run", side_effect=fake_run),
            ):
                payload = live_strategy_runner.run_once(live_settings)

            execution = payload["live_execution"]
            self.assertEqual(provider.fetch_bar_calls, 2)
            self.assertTrue(warning.called)
            self.assertEqual(sleeps, [live_strategy_runner.DEFAULT_LIVE_MARKET_DATA_RETRY_DELAY_SECONDS])
            self.assertEqual(execution["status"], "complete")
            self.assertNotIn("market_data_error", execution)
            self.assertTrue(captured)


if __name__ == "__main__":
    unittest.main()
