from __future__ import annotations

import unittest

from trading_system.research.backtesting.costs import HIGH_COST_CASE, MODERATE_COST_CASE, STRESS_COST_CASE
from trading_system.research.backtesting.metrics import Trade
from trading_system.research.strategy_research import (
    ResearchWindow,
    StrategyDefinition,
    _score_strategy,
    _window_metrics,
)


def sample_definition(name: str) -> StrategyDefinition:
    return StrategyDefinition(
        name=name,
        asset_class="equities",
        universe=("SPY",),
        primary_data_source="Alpaca",
        secondary_data_source=None,
        timeframe="1Day",
        hypothesis="Sample hypothesis",
        features=("momentum",),
        entry_rules=("enter",),
        exit_rules=("exit",),
        stop_loss="3%",
        take_profit="trend exit",
        position_sizing="fixed notional",
        max_positions=1,
        max_daily_trades=1,
        cooldown_rules="none",
        market_regime_filter="risk-on",
        transaction_cost_assumption="moderate",
        slippage_assumption="moderate",
        minimum_data_required="200 bars",
        known_failure_modes=("reversal",),
        implementation_complexity="low",
        recommended_next_step="paper validate",
    )


class StrategyResearchTests(unittest.TestCase):
    def test_window_metrics_records_stress_delta(self) -> None:
        trades = [
            Trade("SPY", 100, 104, 10, holding_period_minutes=390),
            Trade("SPY", 101, 100, 10, holding_period_minutes=390),
        ]
        window = ResearchWindow("recent", "2026-01-01", "2026-02-01")
        evaluation = _window_metrics(
            trades,
            window,
            base_cost_case=MODERATE_COST_CASE,
            stress_cost_case=STRESS_COST_CASE,
            periods_per_year=252.0,
        )
        self.assertGreaterEqual(evaluation.stress_return_delta, 0.0)
        self.assertGreater(evaluation.metrics.trade_count, 0)

    def test_score_strategy_rejects_small_samples(self) -> None:
        trades = [Trade("SPY", 100, 103, 10, holding_period_minutes=390)]
        window = ResearchWindow("recent", "2026-01-01", "2026-02-01")
        evaluation = _window_metrics(
            trades,
            window,
            base_cost_case=MODERATE_COST_CASE,
            stress_cost_case=HIGH_COST_CASE,
            periods_per_year=252.0,
        )
        result = _score_strategy(sample_definition("sample_small"), (evaluation,), implementation_fit=80.0, simplicity=80.0)
        self.assertEqual(result.recommendation, "reject")
        self.assertEqual(result.rejection_reason, "sample size too small")

    def test_score_strategy_can_promote_robust_result(self) -> None:
        profitable_trades = [
            Trade("SPY", 100, 104, 25, holding_period_minutes=390),
            Trade("SPY", 105, 109, 25, holding_period_minutes=390),
            Trade("SPY", 110, 112, 25, holding_period_minutes=390),
            Trade("SPY", 111, 115, 25, holding_period_minutes=390),
            Trade("SPY", 116, 119, 25, holding_period_minutes=390),
            Trade("SPY", 118, 121, 25, holding_period_minutes=390),
        ]
        windows = (
            _window_metrics(profitable_trades, ResearchWindow("w1", "2026-01-01", "2026-02-01"), base_cost_case=MODERATE_COST_CASE, stress_cost_case=HIGH_COST_CASE, periods_per_year=252.0),
            _window_metrics(profitable_trades, ResearchWindow("w2", "2025-05-01", "2025-08-01"), base_cost_case=MODERATE_COST_CASE, stress_cost_case=HIGH_COST_CASE, periods_per_year=252.0),
        )
        result = _score_strategy(sample_definition("sample_good"), windows, implementation_fit=90.0, simplicity=85.0)
        self.assertIn(result.recommendation, {"paper_validate", "watchlist"})
        self.assertGreater(result.score, 55.0)


if __name__ == "__main__":
    unittest.main()
