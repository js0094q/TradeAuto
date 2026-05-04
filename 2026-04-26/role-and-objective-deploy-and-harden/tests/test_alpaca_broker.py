from __future__ import annotations

import unittest
from types import SimpleNamespace

from trading_system.broker.alpaca_sdk import AlpacaBroker, BrokerUnavailable
from trading_system.config import build_settings


class AlpacaBrokerTests(unittest.TestCase):
    def test_expected_account_number_mismatch_fails_connectivity(self) -> None:
        broker = AlpacaBroker(_settings({"ALPACA_EXPECTED_ACCOUNT_NUMBER": "238880875"}))
        broker.get_account = lambda: SimpleNamespace(account_number="592324054")  # type: ignore[method-assign]
        broker.get_clock = lambda: object()  # type: ignore[method-assign]

        with self.assertRaisesRegex(BrokerUnavailable, "expected 238880875, got 592324054"):
            broker.validate_connectivity()


def _settings(overrides: dict[str, str] | None = None) -> object:
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
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "123",
        "TELEGRAM_ADMIN_CHAT_IDS": "123",
        "JWT_SIGNING_KEY": "jwt",
        "ADMIN_TOKEN": "admin",
        "DASHBOARD_TOKEN": "dashboard",
        "KILL_SWITCH_FILE": "/tmp/kill_switch.enabled",
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
    values.update(overrides or {})
    return build_settings(values)


if __name__ == "__main__":
    unittest.main()
