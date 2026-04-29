from __future__ import annotations

import unittest

from trading_system.data.alpaca_market_data import MarketDataRequest, ReadOnlyAlpacaMarketData
from trading_system.data.models import MarketBar
from trading_system.research.data_layer import fetch_historical_bars


class ResearchDataLayerTests(unittest.TestCase):
    def test_fetch_historical_bars_uses_request_shape_and_normalizes_dict_rows(self) -> None:
        observed: list[MarketDataRequest] = []

        def fetcher(request: MarketDataRequest) -> dict[str, object]:
            observed.append(request)
            return {
                "SPY": [
                    {
                        "timestamp": "2026-01-02T05:00:00Z",
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.5,
                        "close": 101.25,
                        "volume": 1500000,
                        "vwap": 101.1,
                    }
                ]
            }

        layer = ReadOnlyAlpacaMarketData(fetcher=fetcher)
        output = fetch_historical_bars(
            layer,
            symbols=("SPY",),
            asset_class="equity",
            timeframe="1Day",
            start="2026-01-01",
            end="2026-01-31",
        )

        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].symbols, ("SPY",))
        self.assertEqual(observed[0].asset_class, "equity")
        self.assertEqual(output["SPY"][0].close, 101.25)

    def test_fetch_historical_bars_keeps_market_bar_instances(self) -> None:
        expected = MarketBar(
            symbol="QQQ",
            timestamp="2026-01-02T05:00:00Z",
            open=200.0,
            high=201.0,
            low=199.0,
            close=200.5,
            volume=2000000,
            vwap=200.3,
        )

        def fetcher(_: MarketDataRequest) -> dict[str, object]:
            return {"QQQ": [expected]}

        layer = ReadOnlyAlpacaMarketData(fetcher=fetcher)
        output = fetch_historical_bars(
            layer,
            symbols=("QQQ",),
            asset_class="equity",
            timeframe="1Day",
            start="2026-01-01",
            end="2026-01-31",
        )

        self.assertEqual(output["QQQ"], [expected])


if __name__ == "__main__":
    unittest.main()
