from __future__ import annotations

import unittest

from trading_system.config import RiskLimits
from trading_system.trading.order_intents import OrderIntent
from trading_system.trading.risk import AccountState, ExecutionGateState, MarketState, RiskEngine, RiskState


def limits() -> RiskLimits:
    return RiskLimits(
        max_trades_per_day=3,
        max_open_positions=3,
        max_order_notional_usd=100.0,
        max_position_notional_usd=100.0,
        max_daily_loss_usd=25.0,
        max_total_drawdown_usd=100.0,
        max_account_risk_pct=1.0,
    )


class StrategyRiskGateTests(unittest.TestCase):
    def test_kill_switch_blocks_new_entries(self) -> None:
        intent = OrderIntent("equity_etf_trend_regime_v1", "QQQ", "buy", 0.25, 1.0, 50.0, "entry")
        decision = RiskEngine(limits()).evaluate_intent(
            intent,
            AccountState(buying_power=1_000.0, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=True),
            order_type="limit",
            limit_price=50.0,
        )
        self.assertFalse(decision.risk_approved)
        self.assertIn("kill switch is enabled", decision.risk_blocks)

    def test_kill_switch_allows_risk_reducing_exit(self) -> None:
        intent = OrderIntent("equity_etf_trend_regime_v1", "QQQ", "sell", 0.0, None, None, "exit")
        decision = RiskEngine(limits()).evaluate_intent(
            intent,
            AccountState(buying_power=1_000.0, open_positions=1, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=True),
            order_type="limit",
            limit_price=50.0,
        )
        self.assertTrue(decision.risk_approved, decision.risk_blocks)

    def test_live_orders_require_all_explicit_gates(self) -> None:
        intent = OrderIntent("equity_etf_trend_regime_v1", "QQQ", "buy", 0.25, 1.0, 50.0, "entry", mode="live")
        decision = RiskEngine(limits()).evaluate_intent(
            intent,
            AccountState(buying_power=1_000.0, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=False),
            execution=ExecutionGateState(profile="paper"),
            order_type="limit",
            limit_price=50.0,
        )
        self.assertFalse(decision.risk_approved)
        self.assertIn("live profile is required", decision.risk_blocks)
        self.assertIn("ENABLE_LIVE_TRADING must be true", decision.risk_blocks)
        self.assertIn("strategy is not enabled for live", decision.risk_blocks)

    def test_paper_intent_cannot_run_under_live_gate(self) -> None:
        intent = OrderIntent("equity_etf_trend_regime_v1", "QQQ", "buy", 0.25, 1.0, 50.0, "entry", mode="paper")
        decision = RiskEngine(limits()).evaluate_intent(
            intent,
            AccountState(buying_power=1_000.0, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=False),
            execution=ExecutionGateState(profile="live", enable_live_trading=True),
            order_type="limit",
            limit_price=50.0,
        )
        self.assertFalse(decision.risk_approved)
        self.assertIn("paper intent cannot run under live execution gate", decision.risk_blocks)

    def test_risk_engine_rejects_oversized_intent(self) -> None:
        intent = OrderIntent("equity_etf_trend_regime_v1", "QQQ", "buy", 0.25, 1.0, 500.0, "entry")
        decision = RiskEngine(limits()).evaluate_intent(
            intent,
            AccountState(buying_power=1_000.0, market_is_open=True),
            MarketState(),
            RiskState(kill_switch_enabled=False),
            order_type="limit",
            limit_price=500.0,
        )
        self.assertFalse(decision.risk_approved)
        self.assertIn("order notional exceeds limit", decision.risk_blocks)


if __name__ == "__main__":
    unittest.main()
