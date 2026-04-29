from __future__ import annotations

import unittest

from trading_system.research.signals.crypto import crypto_24_7_trend
from trading_system.research.signals.liquidity import relative_volume, spread_quality
from trading_system.research.signals.mean_reversion import rsi_stretch, zscore_reversion
from trading_system.research.signals.momentum import rate_of_change, relative_strength
from trading_system.research.signals.options import iv_rank, options_liquidity_score
from trading_system.research.signals.regime import RegimeLabel, classify_market_regime
from trading_system.research.signals.suppression import suppression_reasons
from trading_system.research.signals.trend import moving_average_trend


class SignalTests(unittest.TestCase):
    def test_trend_and_momentum_are_positive_for_rising_prices(self) -> None:
        prices = [float(value) for value in range(1, 61)]
        self.assertGreater(moving_average_trend(prices, short_window=10, long_window=30).value, 0)
        self.assertGreater(rate_of_change(prices, window=10).value, 0)

    def test_relative_strength_compares_against_benchmark(self) -> None:
        asset = [100, 102, 104, 108]
        benchmark = [100, 101, 102, 103]
        self.assertGreater(relative_strength(asset, benchmark, window=3).value, 0)

    def test_mean_reversion_identifies_stretch(self) -> None:
        prices = [100.0] * 20 + [90.0]
        self.assertGreater(zscore_reversion(prices, window=20).value, 0)
        falling = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86]
        self.assertGreater(rsi_stretch(falling, period=14).value, 0)

    def test_liquidity_suppresses_bad_quotes(self) -> None:
        result = spread_quality(100, 0, max_spread_pct=0.25)
        self.assertTrue(result.suppressed)
        self.assertIn("quote", result.suppression_reason or "")
        self.assertGreater(relative_volume(1500, 1000).value, 0.9)

    def test_options_signals_are_confirmation_only(self) -> None:
        liquid = options_liquidity_score(volume=2000, open_interest=5000, bid=1.00, ask=1.01)
        self.assertFalse(liquid.suppressed)
        self.assertGreater(iv_rank(current_iv=0.40, iv_low=0.20, iv_high=0.50).value, 0.6)

    def test_crypto_signal_has_separate_spread_suppression(self) -> None:
        prices = [100.0 + value for value in range(30)]
        result = crypto_24_7_trend(prices, window=24, spread_pct=1.0, max_spread_pct=0.5)
        self.assertTrue(result.suppressed)
        self.assertEqual(result.value, 0.0)

    def test_regime_classifier_returns_no_trade_rules_for_stress(self) -> None:
        prices = [100.0 + value for value in range(60)]
        regime = classify_market_regime(prices, prices, realized_volatility_pct=40)
        self.assertEqual(regime.label, RegimeLabel.HIGH_VOLATILITY)
        self.assertLess(regime.sizing_adjustment, 1.0)

    def test_suppression_reasons_fail_closed_by_default(self) -> None:
        reasons = suppression_reasons(data_is_stale=True, strategy_enabled=False)
        self.assertIn("strategy is disabled by default", reasons)
        self.assertIn("data is stale", reasons)


if __name__ == "__main__":
    unittest.main()
