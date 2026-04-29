from __future__ import annotations

import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from trading_system.config import build_settings

REQUESTS_AVAILABLE = find_spec("requests") is not None
if REQUESTS_AVAILABLE:
    from trading_system.telegram.bot import TelegramCommandHandler, get_updates, message_from_update


def settings_values(kill_file: Path) -> dict[str, str]:
    return {
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
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "1",
        "TELEGRAM_ADMIN_CHAT_IDS": "1",
        "JWT_SIGNING_KEY": "jwt",
        "ADMIN_TOKEN": "admin",
        "DASHBOARD_TOKEN": "dashboard",
        "LOG_LEVEL": "INFO",
        "KILL_SWITCH_FILE": str(kill_file),
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


@unittest.skipUnless(REQUESTS_AVAILABLE, "requests is not installed")
class TelegramBotTests(unittest.TestCase):
    def test_message_from_update_handles_authorized_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kill_file = Path(directory) / "kill_switch.enabled"
            kill_file.write_text("enabled\n", encoding="utf-8")
            handler = TelegramCommandHandler(build_settings(settings_values(kill_file)))

            message = message_from_update(
                handler,
                {"update_id": 10, "message": {"chat": {"id": 1}, "text": "/health"}},
            )

        self.assertIsNotNone(message)
        assert message is not None
        self.assertEqual(message.chat_id, "1")
        self.assertIn('"ok": true', message.text)

    def test_message_from_update_ignores_non_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            kill_file = Path(directory) / "kill_switch.enabled"
            kill_file.write_text("enabled\n", encoding="utf-8")
            handler = TelegramCommandHandler(build_settings(settings_values(kill_file)))

            message = message_from_update(
                handler,
                {"update_id": 10, "message": {"chat": {"id": 1}, "text": "hello"}},
            )

        self.assertIsNone(message)

    def test_get_updates_rejects_invalid_result_shape(self) -> None:
        with patch("trading_system.telegram.bot.telegram_api_request", return_value={"ok": True, "result": {}}):
            with self.assertRaisesRegex(RuntimeError, "invalid result"):
                get_updates("token", None, timeout_seconds=1)


if __name__ == "__main__":
    unittest.main()
