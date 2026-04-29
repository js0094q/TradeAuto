from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_system.data.binance_public_data import BinancePublicDataProvider
from trading_system.data.provider import DataCache


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[list[list[object]]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, params: dict[str, object], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.responses.pop(0))


class BinancePublicDataProviderTests(unittest.TestCase):
    def test_fetch_spot_bars_paginates_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session = FakeSession(
                [
                    [
                        [1000, "1", "2", "0.5", "1.5", "100"],
                        [2000, "1.5", "2.5", "1", "2", "120"],
                    ],
                    [
                        [3000, "2", "3", "1.5", "2.5", "140"],
                    ],
                ]
            )
            provider = BinancePublicDataProvider(
                session=session,
                cache=DataCache(Path(tmpdir) / "cache", ttl_seconds=3_600),
                default_limit=2,
            )
            bars = provider.fetch_spot_bars("BTCUSDT", interval="1h", start_ms=1000, end_ms=3000, limit=2)
            self.assertEqual([int(bar.timestamp) for bar in bars], [1000, 2000, 3000])
            self.assertEqual(bars[-1].close, 2.5)
            self.assertEqual(len(session.calls), 2)


if __name__ == "__main__":
    unittest.main()
