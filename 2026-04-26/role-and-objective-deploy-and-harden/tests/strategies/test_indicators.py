from __future__ import annotations

import math
import unittest

from tests.strategies.helpers import bars_from_prices
from trading_system.strategies.indicators import (
    atr,
    ema,
    mean_reversion_z_score,
    realized_volatility,
    relative_volume,
    rolling_return,
    rolling_z_score,
    rsi,
    sma,
    spread_bps,
)


class IndicatorTests(unittest.TestCase):
    def test_sma_ema_rsi_and_atr_have_expected_direction(self) -> None:
        prices = [float(index) for index in range(1, 80)]
        self.assertEqual(sma(prices, 5), 77.0)
        self.assertGreater(ema(prices, 20), ema(prices, 50))
        self.assertEqual(rsi(prices, 14), 100.0)
        self.assertGreater(atr(bars_from_prices("SPY", prices), 14) or 0.0, 0.0)

    def test_returns_volatility_volume_and_spread(self) -> None:
        prices = [100.0 + index for index in range(80)]
        self.assertGreater(rolling_return(prices, 60) or 0.0, 0.0)
        self.assertGreater(realized_volatility(prices, 20) or 0.0, 0.0)
        self.assertGreater(relative_volume(bars_from_prices("SPY", prices), 20) or 0.0, 0.0)
        self.assertAlmostEqual(spread_bps({"bid": 100.0, "ask": 100.1}) or 0.0, 9.995, places=2)

    def test_z_score_conventions_are_explicit(self) -> None:
        prices = [100.0] * 19 + [95.0]
        self.assertLess(rolling_z_score(prices, 20) or 0.0, 0.0)
        self.assertGreater(mean_reversion_z_score(prices, mean_window=5, z_window=20) or 0.0, 0.0)

    def test_insufficient_history_and_nan_are_safe(self) -> None:
        self.assertIsNone(sma([1.0, 2.0], 3))
        self.assertIsNone(ema([1.0, math.nan, 3.0], 2))
        self.assertIsNone(rolling_return([1.0, 2.0], 5))
        self.assertIsNone(spread_bps({"bid": 0.0, "ask": 100.0}))


if __name__ == "__main__":
    unittest.main()
