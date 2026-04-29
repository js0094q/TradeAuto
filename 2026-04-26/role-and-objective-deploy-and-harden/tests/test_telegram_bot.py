from __future__ import annotations

import os
import unittest
from importlib.util import find_spec
from unittest.mock import patch


TELEGRAM_DEPS_AVAILABLE = find_spec("httpx") is not None and find_spec("telegram") is not None

if TELEGRAM_DEPS_AVAILABLE:
    from trading_system.telegram.bot import (
        HEALTH_PATHS,
        KILL_SWITCH_PATHS,
        PAPER_STRATEGY_PATHS,
        STATUS_PATHS,
        _api_headers,
        _format_payload,
        _summarize_paper_orders,
        _summarize_paper_strategy,
    )


@unittest.skipUnless(TELEGRAM_DEPS_AVAILABLE, "telegram runtime dependencies are not installed")
class TelegramBotTests(unittest.TestCase):
    def test_bot_uses_existing_api_routes(self) -> None:
        self.assertEqual(HEALTH_PATHS, ["/health"])
        self.assertEqual(STATUS_PATHS, ["/ready", "/metrics", "/health"])
        self.assertEqual(KILL_SWITCH_PATHS, ["/admin/kill"])
        self.assertEqual(PAPER_STRATEGY_PATHS, ["/paper-strategy"])

    def test_api_headers_include_admin_token_aliases(self) -> None:
        with patch.dict(os.environ, {"ADMIN_TOKEN": "secret"}, clear=True):
            headers = _api_headers()

        self.assertEqual(headers["X-Admin-Token"], "secret")
        self.assertEqual(headers["X-Control-Token"], "secret")
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_format_payload_truncates_long_responses(self) -> None:
        text = _format_payload({"value": "x" * 4000})

        self.assertIn("...[truncated]", text)
        self.assertLess(len(text), 3600)

    def test_order_summary_includes_buy_and_sell_rows(self) -> None:
        text = _summarize_paper_orders(
            {
                "paper_execution": {
                    "status": "complete",
                    "orders": [
                        {"side": "buy", "symbol": "QQQ", "status": "submitted", "qty": 2, "notional_usd": 100.0, "target_notional_usd": 150.0},
                        {"side": "sell", "symbol": "XLE", "status": "submitted", "qty": 1, "notional_usd": 50.0},
                    ],
                }
            }
        )

        self.assertIn("BUY QQQ", text)
        self.assertIn("SELL XLE", text)

    def test_strategy_summary_reports_sell_submissions(self) -> None:
        text = _summarize_paper_strategy(
            {
                "status": "available",
                "timestamp": "2026-04-29T19:00:00Z",
                "paper_execution": {
                    "status": "complete",
                    "orders": [
                        {"side": "buy", "submitted": True},
                        {"side": "sell", "submitted": True},
                        {"side": "sell", "submitted": False},
                    ],
                },
                "strategies": [{"selected": [{"symbol": "QQQ"}], "exits": [{"symbol": "XLE"}]}],
            }
        )

        self.assertIn("Submitted buys: 1", text)
        self.assertIn("Submitted sells: 1", text)


if __name__ == "__main__":
    unittest.main()
