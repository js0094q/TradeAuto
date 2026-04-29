from __future__ import annotations

import unittest

from trading_system.data.alpaca_market_data import MarketDataProviderError, MarketDataRequest, ReadOnlyAlpacaMarketData
from trading_system.data.rate_limits import RateLimitGuard


class FakeClock:
    def __init__(self) -> None:
        self.now = 1.0

    def __call__(self) -> float:
        return self.now


class AlpacaMarketDataTests(unittest.TestCase):
    def test_requires_configured_read_only_fetcher(self) -> None:
        client = ReadOnlyAlpacaMarketData()
        request = MarketDataRequest(symbols=("SPY",), asset_class="etf", timeframe="1Day", start="2020-01-01")
        with self.assertRaises(MarketDataProviderError):
            client.historical_bars(request)

    def test_fetches_then_serves_cached_market_data(self) -> None:
        clock = FakeClock()
        calls = {"count": 0}

        def fetcher(request: MarketDataRequest) -> dict[str, object]:
            calls["count"] += 1
            return {request.symbols[0]: [{"close": 100.0}]}

        client = ReadOnlyAlpacaMarketData(
            fetcher=fetcher,
            rate_limit=RateLimitGuard(max_calls=10, period_seconds=60, clock=clock),
            clock=clock,
        )
        request = MarketDataRequest(symbols=("SPY",), asset_class="etf", timeframe="1Day", start="2020-01-01")
        first = client.historical_bars(request)
        second = client.historical_bars(request)
        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
