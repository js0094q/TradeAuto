from __future__ import annotations

from datetime import date, timedelta
import unittest

from trading_system.data.models import MarketBar
from trading_system.research.focused_candidate_backtest import (
    _atr_sized_quantity,
    _ema,
    _relative_volume,
    _rsi,
    _simulate_default_stack_rotation,
)


def sample_bars(symbol: str, *, start: date, length: int, base: float, drift: float) -> list[MarketBar]:
    bars: list[MarketBar] = []
    for index in range(length):
        close = base + drift * index
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=(start + timedelta(days=index)).isoformat(),
                open=close * 0.998,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1_000_000 + index * 1_000,
            )
        )
    return bars


class FocusedCandidateBacktestTests(unittest.TestCase):
    def test_default_stack_rotation_generates_research_trade(self) -> None:
        start = date(2025, 1, 1)
        bars = {
            "SPY": sample_bars("SPY", start=start, length=240, base=500.0, drift=1.0),
            "QQQ": sample_bars("QQQ", start=start, length=240, base=400.0, drift=1.4),
        }
        trades = _simulate_default_stack_rotation(
            bars,
            activation_start=(start + timedelta(days=210)).isoformat(),
            universe=("QQQ",),
            strategy_name="test_default_stack",
        )
        self.assertGreaterEqual(len(trades), 1)
        self.assertEqual(trades[0].sector, "default_stack_rotation")
        self.assertGreater(trades[0].quantity, 0.0)

    def test_indicator_helpers_have_expected_directionality(self) -> None:
        rising = [100.0 + index for index in range(60)]
        flat_then_rising = [100.0] * 30 + [101.0 + index for index in range(30)]
        self.assertGreater(_ema(rising, 20), _ema(rising, 50))
        self.assertGreater(_rsi(flat_then_rising, 14), 50.0)

    def test_relative_volume_and_atr_sizing_are_bounded(self) -> None:
        start = date(2025, 1, 1)
        bars = sample_bars("SPY", start=start, length=30, base=100.0, drift=0.2)
        self.assertGreater(_relative_volume(bars, 20), 0.0)
        quantity = _atr_sized_quantity(100.0, 2.0, risk_dollars=250.0, notional_cap=10_000.0)
        self.assertLessEqual(quantity * 100.0, 10_000.0)


if __name__ == "__main__":
    unittest.main()
