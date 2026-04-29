from __future__ import annotations

import unittest

from trading_system.research.rejection import StrategyEvidence, evaluate_rejection


def passing_evidence() -> StrategyEvidence:
    return StrategyEvidence(
        name="candidate",
        slippage_adjusted_return=0.05,
        symbols_tested=25,
        regimes_tested=5,
        trade_count=500,
        max_drawdown_pct=0.05,
        allowed_drawdown_pct=0.10,
        parameter_stability=0.80,
        outlier_regime_dependency=False,
        data_quality_gaps=False,
        realtime_data_available=True,
        explainable_entry=True,
        explainable_avoidance=True,
        execution_assumptions_realistic=True,
        bounded_risk=True,
        kill_switch_can_respond_before_max_loss=True,
        independently_disableable=True,
        requires_manual_interpretation=False,
        stale_data_fails_closed=True,
        turnover=2.0,
        max_turnover=5.0,
        spread_liquidity_passed=True,
        no_trade_conditions_defined=True,
    )


class RejectionRuleTests(unittest.TestCase):
    def test_rejects_unprofitable_after_slippage_and_small_sample(self) -> None:
        evidence = passing_evidence().__dict__ | {"slippage_adjusted_return": -0.01, "symbols_tested": 1}
        decision = evaluate_rejection(StrategyEvidence(**evidence))
        self.assertTrue(decision.rejected)
        self.assertIn("performance disappears after realistic slippage", decision.reasons)
        self.assertIn("performance depends on too few symbols", decision.reasons)

    def test_accepts_research_evidence_that_avoids_hard_rejection_rules(self) -> None:
        decision = evaluate_rejection(passing_evidence())
        self.assertFalse(decision.rejected, decision.reasons)


if __name__ == "__main__":
    unittest.main()

