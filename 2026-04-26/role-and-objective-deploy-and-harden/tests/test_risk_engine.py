from __future__ import annotations

import unittest

from trading_system.config import RiskLimits
from trading_system.trading.risk import AccountState, MarketState, OrderRequest, RiskEngine, RiskState


def limits() -> RiskLimits:
    return RiskLimits(
        max_trades_per_day=3,
        max_open_positions=3,
        max_order_notional_usd=25,
        max_position_notional_usd=50,
        max_daily_loss_usd=25,
        max_total_drawdown_usd=100,
        max_account_risk_pct=1.0,
    )


class RiskEngineTests(unittest.TestCase):
    def test_kill_switch_rejects_order(self) -> None:
        engine = RiskEngine(limits())
        decision = engine.evaluate(
            OrderRequest("AAPL", "buy", 1, "limit", 10),
            AccountState(buying_power=100, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=True),
        )
        self.assertFalse(decision.approved)
        self.assertIn("kill switch is enabled", decision.reasons)

    def test_market_order_rejected_by_default(self) -> None:
        engine = RiskEngine(limits())
        decision = engine.evaluate(
            OrderRequest("AAPL", "buy", 1, "market", None, notional_usd=10),
            AccountState(buying_power=100, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=False),
        )
        self.assertFalse(decision.approved)
        self.assertIn("limit orders are required", decision.reasons)

    def test_small_limit_order_can_pass(self) -> None:
        engine = RiskEngine(limits())
        decision = engine.evaluate(
            OrderRequest("AAPL", "buy", 1, "limit", 10),
            AccountState(buying_power=100, market_is_open=True),
            MarketState(asset_tradable=True, spread_pct=0.1, volume=1000000, min_volume=100000),
            RiskState(kill_switch_enabled=False),
        )
        self.assertTrue(decision.approved, decision.reasons)


if __name__ == "__main__":
    unittest.main()

