from __future__ import annotations

import unittest

from trading_system.research.backtesting.costs import BASE_COST_CASE, STRESS_COST_CASE, estimate_round_trip_cost
from trading_system.research.backtesting.metrics import Trade, calculate_metrics
from trading_system.research.backtesting.slippage import SlippageAssumptions, adjusted_fill_price


class BacktestingMetricsTests(unittest.TestCase):
    def test_cost_model_charges_spread_slippage_and_rejections(self) -> None:
        base = estimate_round_trip_cost(10_000, 100, assumptions=BASE_COST_CASE)
        stress = estimate_round_trip_cost(10_000, 100, assumptions=STRESS_COST_CASE)
        self.assertGreater(stress, base)

    def test_slippage_adjusts_buy_price_up_and_sell_price_down(self) -> None:
        assumptions = SlippageAssumptions(spread_bps=5, slippage_bps=5)
        self.assertGreater(adjusted_fill_price(100, side="buy", assumptions=assumptions), 100)
        self.assertLess(adjusted_fill_price(100, side="sell", assumptions=assumptions), 100)

    def test_metrics_include_required_risk_outputs(self) -> None:
        trades = [
            Trade("SPY", 100, 105, 10, holding_period_minutes=60, regime="risk_on", entry_time_of_day="open"),
            Trade("SPY", 105, 103, 10, holding_period_minutes=30, regime="risk_on", entry_time_of_day="midday"),
            Trade("QQQ", 100, 101, 5, holding_period_minutes=45, regime="mixed", entry_time_of_day="close"),
        ]
        metrics = calculate_metrics(trades, starting_equity=100_000, assumptions=BASE_COST_CASE)
        self.assertEqual(metrics.trade_count, 3)
        self.assertGreater(metrics.turnover, 0)
        self.assertIn("SPY", metrics.by_symbol)
        self.assertIn("risk_on", metrics.by_regime)
        self.assertGreaterEqual(metrics.longest_losing_streak, 0)


if __name__ == "__main__":
    unittest.main()

