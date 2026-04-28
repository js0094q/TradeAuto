from __future__ import annotations

import unittest

from trading_system.strategy.base import StrategyMetrics
from trading_system.strategy.promotion import PromotionEvidence, evaluate_promotion
from trading_system.strategy.registry import default_registry
from trading_system.strategy.scoring import rank_strategies


class StrategyTests(unittest.TestCase):
    def test_registry_contains_required_families(self) -> None:
        names = default_registry().names()
        self.assertIn("momentum_continuation", names)
        self.assertIn("earnings_news_avoidance", names)

    def test_ranking_prefers_stronger_out_of_sample_strategy(self) -> None:
        ranked = rank_strategies(
            [
                StrategyMetrics(name="weak", sharpe=0.2, sortino=0.2, max_drawdown=30, live_readiness=0.4),
                StrategyMetrics(
                    name="strong",
                    sharpe=2.0,
                    sortino=1.5,
                    max_drawdown=5,
                    profit_factor=1.8,
                    win_rate=0.58,
                    execution_reliability=0.99,
                    regime_robustness=0.8,
                    live_readiness=0.9,
                ),
            ]
        )
        self.assertEqual(ranked[0].name, "strong")

    def test_promotion_requires_all_safety_evidence(self) -> None:
        decision = evaluate_promotion(PromotionEvidence(unit_tests_passed=True, backtest_passed=True))
        self.assertFalse(decision.approved)
        self.assertIn("kill_switch_passed", decision.missing)


if __name__ == "__main__":
    unittest.main()

