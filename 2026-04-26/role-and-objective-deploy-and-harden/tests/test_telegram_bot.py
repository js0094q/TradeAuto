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
        STATUS_PATHS,
        _api_headers,
        _format_payload,
    )


@unittest.skipUnless(TELEGRAM_DEPS_AVAILABLE, "telegram runtime dependencies are not installed")
class TelegramBotTests(unittest.TestCase):
    def test_bot_uses_existing_api_routes(self) -> None:
        self.assertEqual(HEALTH_PATHS, ["/health"])
        self.assertEqual(STATUS_PATHS, ["/ready", "/metrics", "/health"])
        self.assertEqual(KILL_SWITCH_PATHS, ["/admin/kill"])

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


if __name__ == "__main__":
    unittest.main()
