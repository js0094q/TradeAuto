from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_system.config import build_settings
from trading_system.health import live_strategy_status_payload, metrics_payload, paper_strategy_status_payload, readiness_payload


class HealthReadinessTests(unittest.TestCase):
    def test_paper_cli_mode_does_not_require_sdk_connectivity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            kill_switch = Path(tmpdir) / "kill_switch.enabled"
            kill_switch.write_text("disabled\n", encoding="utf-8")
            settings = build_settings(
                {
                    "APP_ENV": "paper",
                    "TRADING_MODE": "paper",
                    "LIVE_TRADING_ENABLED": "false",
                    "HOST": "127.0.0.1",
                    "POSTGRES_URL": "postgresql://trader_app:test@127.0.0.1:5432/trading_system_paper",
                    "REDIS_URL": "redis://127.0.0.1:6379/1",
                    "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
                    "ALPACA_CLI_ENABLED": "true",
                    "TELEGRAM_BOT_TOKEN": "token",
                    "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                    "TELEGRAM_ADMIN_CHAT_IDS": "123",
                    "JWT_SIGNING_KEY": "jwt",
                    "ADMIN_TOKEN": "admin",
                    "DASHBOARD_TOKEN": "dashboard",
                    "LOG_DIR": tmpdir,
                    "KILL_SWITCH_FILE": str(kill_switch),
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
            payload = readiness_payload(settings, external=True)
        sdk_check = next(item for item in payload["checks"] if item["name"] == "alpaca_sdk_connectivity")
        self.assertTrue(sdk_check["ok"])
        self.assertEqual(sdk_check["detail"], "skipped for paper CLI mode")

    def test_paper_strategy_status_bootstraps_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _paper_settings(tmpdir)
            payload = paper_strategy_status_payload(settings)
            self.assertTrue((Path(tmpdir) / "state" / "paper_strategy_status.json").exists())
            self.assertTrue((Path(tmpdir) / "state" / "paper_entry_orders.json").exists())
            self.assertTrue((Path(tmpdir) / "state" / "kill_switch.enabled").exists())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["strategies"], [])

    def test_paper_strategy_status_updates_metrics_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            state_dir.mkdir()
            (state_dir / "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            (state_dir / "paper_strategy_status.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "mode": "paper",
                        "timestamp": "2026-04-29T12:00:00Z",
                        "kill_switch_enabled": False,
                        "paper_execution": {"status": "complete", "market_open": True},
                        "strategies": [
                            {
                                "strategy_name": "equity_etf_trend_regime_v1",
                                "mode": "paper",
                                "selected": [{"symbol": "SPY", "target_weight": 0.25, "reason": "trend"}],
                                "risk_blocks": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings = _paper_settings(tmpdir)
            payload = paper_strategy_status_payload(settings)
            metrics = metrics_payload(settings)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["strategies"][0]["strategy_name"], "equity_etf_trend_regime_v1")
        self.assertEqual(metrics["active_strategy"], "equity_etf_trend_regime_v1")
        self.assertEqual(metrics["market_open_status"], "open")
        self.assertEqual(metrics["data_freshness"], "2026-04-29T12:00:00Z")

    def test_live_strategy_status_updates_live_metrics_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            log_dir = Path(tmpdir) / "logs"
            state_dir.mkdir()
            log_dir.mkdir()
            (state_dir / "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            live_payload = {
                "ok": True,
                "mode": "live",
                "timestamp": "2026-04-30T13:30:00Z",
                "kill_switch_enabled": False,
                "live_execution": {
                    "status": "complete",
                    "market_open": True,
                    "runtime_gate_passed": True,
                    "orders": [{"symbol": "QQQ", "side": "buy", "status": "submitted", "submitted": True}],
                },
                "strategies": [
                    {
                        "strategy_name": "equity_etf_trend_regime_v1",
                        "mode": "live",
                        "selected": [{"symbol": "QQQ", "target_weight": 0.25, "reason": "trend"}],
                        "risk_blocks": [],
                    }
                ],
            }
            (state_dir / "live_strategy_status.json").write_text(json.dumps(live_payload), encoding="utf-8")
            (state_dir / "live_strategy_orders.json").write_text(
                json.dumps({"client_order_ids": ["etrv1-20260430-QQQ-live-entry"]}),
                encoding="utf-8",
            )
            (log_dir / "live.err.log").write_text(
                "2026-04-30 13:29:15,238 ERROR market data unavailable\n",
                encoding="utf-8",
            )
            (log_dir / "live_strategy_rebalances.jsonl").write_text(json.dumps(live_payload) + "\n", encoding="utf-8")
            settings = _paper_settings(
                tmpdir,
                {
                    "APP_ENV": "live",
                    "TRADING_MODE": "live",
                    "LIVE_TRADING_ENABLED": "true",
                    "ALPACA_BASE_URL": "https://api.alpaca.markets",
                    "ALPACA_API_KEY": "key",
                    "ALPACA_API_SECRET": "secret",
                    "ALPACA_CLI_PROFILE": "live",
                },
            )
            payload = live_strategy_status_payload(settings)
            metrics = metrics_payload(settings)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "available")
        self.assertEqual(metrics["active_strategy"], "equity_etf_trend_regime_v1")
        self.assertEqual(metrics["market_open_status"], "open")
        self.assertEqual(metrics["data_freshness"], "2026-04-30T13:30:00Z")
        self.assertEqual(metrics["live_execution_status"], "complete")
        self.assertTrue(metrics["live_runtime_gate_passed"])
        self.assertEqual(metrics["last_trade_time"], "2026-04-30T13:30:00Z")
        self.assertEqual(metrics["open_orders"], 1)
        self.assertIsNone(metrics["latest_live_error"])

    def test_live_strategy_mode_start_suppresses_prior_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            log_dir = Path(tmpdir) / "logs"
            state_dir.mkdir()
            log_dir.mkdir()
            (state_dir / "kill_switch.enabled").write_text("disabled\n", encoding="utf-8")
            live_payload = {
                "ok": True,
                "mode": "live",
                "timestamp": "2026-05-04T15:38:23Z",
                "live_execution": {"status": "complete", "market_open": True, "runtime_gate_passed": True},
                "strategies": [],
            }
            (state_dir / "live_strategy_status.json").write_text(json.dumps(live_payload), encoding="utf-8")
            (log_dir / "live.err.log").write_text(
                "\n".join(
                    (
                        "Traceback (most recent call last):",
                        "subprocess.TimeoutExpired: old quote timeout",
                        "2026-05-04 15:38:11,234 INFO trading engine started in live strategy mode",
                        "2026-05-04 15:38:23,976 INFO live strategy cycle complete selected=XLK live_execution=complete",
                    )
                ),
                encoding="utf-8",
            )
            settings = _paper_settings(
                tmpdir,
                {
                    "APP_ENV": "live",
                    "TRADING_MODE": "live",
                    "LIVE_TRADING_ENABLED": "true",
                    "ALPACA_BASE_URL": "https://api.alpaca.markets",
                    "ALPACA_API_KEY": "key",
                    "ALPACA_API_SECRET": "secret",
                    "ALPACA_CLI_PROFILE": "live",
                },
            )
            metrics = metrics_payload(settings)
        self.assertIsNone(metrics["latest_live_error"])


def _paper_settings(tmpdir: str, overrides: dict[str, str] | None = None) -> object:
    values = {
            "APP_ENV": "paper",
            "TRADING_MODE": "paper",
            "LIVE_TRADING_ENABLED": "false",
            "HOST": "127.0.0.1",
            "POSTGRES_URL": "postgresql://trader_app:test@127.0.0.1:5432/trading_system_paper",
            "REDIS_URL": "redis://127.0.0.1:6379/1",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
            "ALPACA_CLI_ENABLED": "true",
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
    values.update(overrides or {})
    return build_settings(values)


if __name__ == "__main__":
    unittest.main()
