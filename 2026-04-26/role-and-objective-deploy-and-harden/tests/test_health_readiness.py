from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_system.config import build_settings
from trading_system.health import readiness_payload


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


if __name__ == "__main__":
    unittest.main()
