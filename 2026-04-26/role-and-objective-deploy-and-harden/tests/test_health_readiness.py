from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_system.config import build_settings
from trading_system.health import metrics_payload, paper_strategy_status_payload, readiness_payload


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

    def test_paper_strategy_status_reports_missing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _paper_settings(tmpdir)
            payload = paper_strategy_status_payload(settings)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "missing")
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


def _paper_settings(tmpdir: str) -> object:
    return build_settings(
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


if __name__ == "__main__":
    unittest.main()
