from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_system.config import build_settings, validate_settings


BASE_ENV = {
    "APP_ENV": "live",
    "TRADING_MODE": "live",
    "LIVE_TRADING_ENABLED": "true",
    "HOST": "127.0.0.1",
    "PORT": "8000",
    "POSTGRES_URL": "postgresql://trader_app:secret@127.0.0.1:5432/trading_system",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "ALPACA_API_KEY": "key",
    "ALPACA_API_SECRET": "secret",
    "ALPACA_BASE_URL": "https://api.alpaca.markets",
    "ALPACA_DATA_FEED": "iex",
    "ALPACA_CLI_ENABLED": "true",
    "ALPACA_CLI_PROFILE": "live",
    "TELEGRAM_BOT_TOKEN": "token",
    "TELEGRAM_ALLOWED_CHAT_IDS": "1",
    "TELEGRAM_ADMIN_CHAT_IDS": "1",
    "JWT_SIGNING_KEY": "jwt",
    "ADMIN_TOKEN": "admin",
    "DASHBOARD_TOKEN": "dashboard",
    "LOG_LEVEL": "INFO",
    "KILL_SWITCH_ENABLED": "false",
    "MAX_TRADES_PER_DAY": "3",
    "MAX_OPEN_POSITIONS": "3",
    "MAX_ORDER_NOTIONAL_USD": "25",
    "MAX_POSITION_NOTIONAL_USD": "50",
    "MAX_DAILY_LOSS_USD": "25",
    "MAX_TOTAL_DRAWDOWN_USD": "100",
    "MAX_ACCOUNT_RISK_PCT": "1.0",
    "REQUIRE_LIMIT_ORDERS": "true",
    "ALLOW_MARKET_ORDERS": "false",
    "ALLOW_SHORT_SELLING": "false",
    "ALLOW_OPTIONS_TRADING": "false",
    "ALLOW_CRYPTO_TRADING": "false",
    "HEALTH_CHECKS_ENABLED": "true",
}


class ValidateEnvTests(unittest.TestCase):
    def test_live_rejects_paper_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kill_file = Path(directory) / "kill_switch.enabled"
            kill_file.write_text("disabled\n", encoding="utf-8")
            values = dict(BASE_ENV, KILL_SWITCH_FILE=str(kill_file), ALPACA_BASE_URL="https://paper-api.alpaca.markets")
            result = validate_settings(build_settings(values), mode="live")
        self.assertFalse(result.ok)
        self.assertIn("live mode must use https://api.alpaca.markets", result.errors)

    def test_live_passes_with_required_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kill_file = Path(directory) / "kill_switch.enabled"
            kill_file.write_text("disabled\n", encoding="utf-8")
            result = validate_settings(build_settings(dict(BASE_ENV, KILL_SWITCH_FILE=str(kill_file))), mode="live")
        self.assertTrue(result.ok, result.errors)

    def test_non_live_rejects_live_flag(self) -> None:
        values = dict(
            BASE_ENV,
            APP_ENV="test",
            TRADING_MODE="paper",
            LIVE_TRADING_ENABLED="true",
            ALPACA_BASE_URL="https://paper-api.alpaca.markets",
        )
        result = validate_settings(build_settings(values), mode="paper")
        self.assertFalse(result.ok)
        self.assertIn("LIVE_TRADING_ENABLED must be false outside live mode", result.errors)


if __name__ == "__main__":
    unittest.main()

