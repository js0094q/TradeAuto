from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from trading_system.data.models import MarketBar
from trading_system.research.patterns import (
    detect_crypto_breakouts,
    detect_etf_time_series_momentum,
    detect_opening_range_breakouts,
    detect_vwap_mean_reversion,
    summarize_observations,
)


def daily_bars(length: int, *, start: float = 100.0, step: float = 1.0, symbol: str = "SPY") -> list[MarketBar]:
    return [
        MarketBar(
            symbol=symbol,
            timestamp=f"2026-01-{(index % 28) + 1:02d}T05:00:00Z",
            open=start + index * step,
            high=start + index * step + 1,
            low=start + index * step - 1,
            close=start + index * step,
            volume=1_000_000,
            vwap=start + index * step,
        )
        for index in range(length)
    ]


def minute_bars(values: list[float], *, symbol: str = "SPY") -> list[MarketBar]:
    start = datetime(2026, 4, 27, 13, 30, tzinfo=timezone.utc)
    bars: list[MarketBar] = []
    for index, value in enumerate(values):
        timestamp = (start + timedelta(minutes=index)).isoformat().replace("+00:00", "Z")
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=timestamp,
                open=value,
                high=value + 0.1,
                low=value - 0.1,
                close=value,
                volume=10_000,
                vwap=value,
            )
        )
    return bars


class PatternMiningTests(unittest.TestCase):
    def test_etf_time_series_detects_fresh_alignment(self) -> None:
        bars = daily_bars(240, start=100.0, step=0.5)
        observations = detect_etf_time_series_momentum({"SPY": bars}, horizon_days=20)
        self.assertGreaterEqual(len(observations), 1)
        self.assertEqual(observations[0].strategy, "etf_time_series_momentum_v1")

    def test_opening_range_breakout_uses_first_post_window_break(self) -> None:
        values = [100.0] * 15 + [100.5, 101.0, 101.2, 101.4, 101.6] + [101.7] * 11
        observations = detect_opening_range_breakouts({"SPY": minute_bars(values)}, opening_minutes=15)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].trigger_type, "15m_opening_range_high_break")

    def test_vwap_reversion_detects_downside_stretch(self) -> None:
        values = [100.0] * 31 + [98.5, 99.0, 99.5, 100.0]
        observations = detect_vwap_mean_reversion({"SPY": minute_bars(values)}, stretch_pct=0.5)
        self.assertEqual(len(observations), 1)
        self.assertLess(observations[0].max_adverse_move_pct, 0)

    def test_crypto_breakout_summary_is_grouped_by_strategy(self) -> None:
        bars = daily_bars(40, start=100.0, step=2.0, symbol="BTC/USD")
        observations = detect_crypto_breakouts({"BTC/USD": bars}, breakout_days=20, horizon_days=5)
        summary = summarize_observations(observations)
        self.assertIn("crypto_trend_breakout_v1", summary)
        self.assertGreater(summary["crypto_trend_breakout_v1"]["observation_count"], 0)


if __name__ == "__main__":
    unittest.main()
