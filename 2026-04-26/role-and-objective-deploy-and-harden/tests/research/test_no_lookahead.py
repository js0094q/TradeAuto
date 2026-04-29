from __future__ import annotations

import unittest

from trading_system.research.signals.base import no_lookahead_window
from trading_system.research.signals.volatility import atr_breakout


class NoLookaheadTests(unittest.TestCase):
    def test_no_lookahead_window_uses_only_prior_observations(self) -> None:
        values = [1, 2, 3, 4, 5]
        self.assertEqual(no_lookahead_window(values, end_exclusive=4, window=2), (3, 4))

    def test_atr_breakout_excludes_current_bar_range_from_prior_atr(self) -> None:
        highs = [11, 12, 13, 14, 15, 16, 100]
        lows = [9, 10, 11, 12, 13, 14, 1]
        closes = [10, 11, 12, 13, 14, 15, 16]
        baseline = atr_breakout(highs, lows, closes, window=3)
        changed_current_range = atr_breakout([*highs[:-1], 1_000], [*lows[:-1], 0.1], closes, window=3)
        self.assertEqual(baseline.inputs_used["prior_atr"], changed_current_range.inputs_used["prior_atr"])
        self.assertEqual(baseline.value, changed_current_range.value)


if __name__ == "__main__":
    unittest.main()

