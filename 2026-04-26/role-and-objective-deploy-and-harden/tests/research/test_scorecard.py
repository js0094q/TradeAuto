from __future__ import annotations

import unittest

from trading_system.research.scorecard import SCORECARD_DIMENSIONS, StrategyScorecard
from trading_system.strategy.base import PromotionStage
from trading_system.strategy.registry import default_registry


def scores(value: int) -> dict[str, int]:
    return {dimension: value for dimension in SCORECARD_DIMENSIONS}


class ScorecardTests(unittest.TestCase):
    def test_scorecard_requires_total_score_and_mandatory_minimums(self) -> None:
        card = StrategyScorecard("momentum_v1", scores(4))
        self.assertGreaterEqual(card.total_score, 35)
        self.assertTrue(card.eligible_for_restricted_live_review)
        weak = StrategyScorecard("weak", scores(4) | {"robustness": 3})
        self.assertFalse(weak.eligible_for_restricted_live_review)
        self.assertIn("robustness", weak.mandatory_failures)

    def test_strategy_must_default_disabled_for_live_candidate_review(self) -> None:
        card = StrategyScorecard("unsafe", scores(5), strategy_default_disabled=False)
        self.assertFalse(card.eligible_for_restricted_live_review)
        self.assertIn("strategy default-disabled control missing", card.mandatory_failures)

    def test_existing_registry_strategies_default_to_research_only(self) -> None:
        registry = default_registry()
        self.assertEqual(registry.get("momentum_continuation").stage, PromotionStage.RESEARCH_ONLY)


if __name__ == "__main__":
    unittest.main()
