from __future__ import annotations

import unittest

from trading_system.research.backtesting.splits import assert_chronological_no_lookahead, train_validation_test_split
from trading_system.research.backtesting.walk_forward import build_walk_forward_windows


class WalkForwardTests(unittest.TestCase):
    def test_walk_forward_windows_advance_without_overlap(self) -> None:
        observations = list(range(20))
        windows = build_walk_forward_windows(observations, train_size=8, test_size=4, step_size=4)
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0].train, tuple(range(8)))
        self.assertEqual(windows[0].test, tuple(range(8, 12)))
        self.assertEqual(windows[1].train_start_index, 4)

    def test_train_validation_test_split_is_chronological(self) -> None:
        observations = list(range(100))
        split = train_validation_test_split(observations)
        assert_chronological_no_lookahead(split.train, split.validation, split.test, key=lambda value: value)
        self.assertLess(split.train[-1], split.validation[0])
        self.assertLess(split.validation[-1], split.test[0])


if __name__ == "__main__":
    unittest.main()

