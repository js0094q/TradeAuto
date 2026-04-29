from __future__ import annotations

import unittest

from trading_system.strategies import (
    CryptoTrendBreakoutV1,
    CrossSectionalMomentumRotationV1,
    EtfTimeSeriesMomentumV1,
    OpeningRangeBreakoutV1,
    PostEarningsDriftV1,
    VwapMeanReversionV1,
)
from trading_system.strategy.registry import default_registry


def sample_prices(start: float = 100.0, length: int = 260, drift: float = 0.02) -> list[float]:
    return [start + i * drift for i in range(length)]


def sample_volumes(length: int = 260, start: int = 1_000_000) -> list[float]:
    return [start + i * 1000 for i in range(length)]


class StrategyCandidateSignalTests(unittest.TestCase):
    def test_all_strategies_registered(self) -> None:
        registry = default_registry()
        self.assertIn("etf_time_series_momentum_v1", registry.names())
        self.assertIn("cross_sectional_momentum_rotation_v1", registry.names())
        self.assertIn("opening_range_breakout_v1", registry.names())
        self.assertIn("vwap_mean_reversion_v1", registry.names())
        self.assertIn("post_earnings_drift_v1", registry.names())
        self.assertIn("crypto_trend_breakout_v1", registry.names())

    def test_etf_strategy_entry_and_exit(self) -> None:
        strat = EtfTimeSeriesMomentumV1()
        self.assertFalse(strat.default_enabled)
        closes = sample_prices()
        buy_signal = strat.generate_signal(
            "SPY",
            {
                "close_prices": closes,
                "spread_pct": 0.001,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
                "in_position": False,
            },
        )
        self.assertEqual(buy_signal.direction, "buy")

        exit_signal = strat.generate_signal(
            "SPY",
            {
                "close_prices": closes,
                "spread_pct": 0.001,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
                "in_position": True,
            },
        )
        self.assertEqual(exit_signal.direction, "exit")

    def test_cross_sectional_entry_only_with_top_rank(self) -> None:
        strat = CrossSectionalMomentumRotationV1()
        self.assertFalse(strat.default_enabled)
        signal = strat.generate_signal(
            "QQQ",
            {
                "close_prices": sample_prices(),
                "symbol_rank_percentile": 0.02,
                "relative_volume": 2.0,
                "spread_pct": 0.001,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
            },
        )
        self.assertEqual(signal.direction, "buy")

        suppressed = strat.generate_signal(
            "QQQ",
            {
                "close_prices": sample_prices(),
                "symbol_rank_percentile": 0.9,
                "relative_volume": 2.0,
                "spread_pct": 0.001,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
            },
        )
        self.assertEqual(suppressed.direction, "hold")

    def test_opening_range_and_vwap_reversion_have_stale_guard(self) -> None:
        orb = OpeningRangeBreakoutV1()
        vwap = VwapMeanReversionV1()

        stale_orb = orb.generate_signal(
            "AAPL",
            {
                "opening_range_high": 130.0,
                "opening_range_low": 129.0,
                "high": 129.8,
                "low": 129.2,
                "close": 129.5,
                "atr_now": 1.2,
                "atr_prior": 1.0,
                "spread_pct": 0.001,
                "volume": 100000,
                "volume_baseline": 60000,
                "market_is_open": True,
                "minutes_since_open": 30,
                "market_regime": "risk_on",
                "data_stale": True,
                "in_position": False,
                "minute": 30,
            },
        )
        self.assertEqual(stale_orb.direction, "hold")

        hold = vwap.generate_signal(
            "SPY",
            {
                "close": 690.0,
                "vwap": 695.0,
                "z_score": 0.4,
                "spread_pct": 0.001,
                "trend_day": False,
                "volatility": 1.0,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
                "in_position": False,
                "entry_time_minute": 1,
            },
        )
        self.assertEqual(hold.direction, "hold")

    def test_post_earnings_is_research_only_without_data(self) -> None:
        strat = PostEarningsDriftV1()
        no_data = strat.generate_signal(
            "AAPL",
            {
                "market_is_open": True,
                "market_regime": "risk_on",
                "data_stale": False,
                "earnings_data_available": False,
            },
        )
        self.assertIn("research-only", no_data.reason)

    def test_crypto_blocked_on_weekend(self) -> None:
        strat = CryptoTrendBreakoutV1()
        weekend = strat.generate_signal(
            "BTC/USD",
            {
                "close_prices": sample_prices(89000.0),
                "breakout_level": 89200.0,
                "atr_now": 2000.0,
                "atr_prior": 1500.0,
                "spread_pct": 0.001,
                "is_weekend": True,
                "market_regime": "risk_on",
                "volatility": 2.5,
                "data_stale": False,
            },
        )
        self.assertEqual(weekend.direction, "hold")

    def test_strategy_explain_signal_returns_text(self) -> None:
        strat = VwapMeanReversionV1()
        explanation = strat.explain_signal(
            "SPY",
            {
                "close": 689.0,
                "vwap": 700.0,
                "z_score": 2.0,
                "spread_pct": 0.001,
                "trend_day": False,
                "volatility": 1.0,
                "market_regime": "risk_on",
                "market_is_open": True,
                "data_stale": False,
                "in_position": False,
            },
        )
        self.assertIn("buy", explanation)


if __name__ == "__main__":
    unittest.main()

