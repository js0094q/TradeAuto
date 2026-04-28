from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromotionStage(StrEnum):
    RESEARCH_ONLY = "research_only"
    BACKTEST_ELIGIBLE = "backtest_eligible"
    TEST_EXECUTION_ELIGIBLE = "test_execution_eligible"
    RESTRICTED_LIVE_ELIGIBLE = "restricted_live_eligible"
    EXPANDED_LIVE_ELIGIBLE = "expanded_live_eligible"


@dataclass(frozen=True)
class StrategySignal:
    strategy: str
    symbol: str
    direction: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class StrategyMetrics:
    name: str
    out_of_sample_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    average_trade_return: float = 0.0
    max_loss_per_trade: float = 0.0
    turnover: float = 0.0
    slippage_sensitivity: float = 0.0
    spread_sensitivity: float = 0.0
    regime_robustness: float = 0.0
    execution_reliability: float = 0.0
    trade_frequency: float = 0.0
    live_readiness: float = 0.0
    overfitting_penalty: float = 0.0
    concentration_penalty: float = 0.0


class Strategy:
    name: str
    family: str
    description: str
    stage: PromotionStage = PromotionStage.RESEARCH_ONLY

    def generate_signal(self, symbol: str, features: dict[str, float]) -> StrategySignal:
        return StrategySignal(
            strategy=self.name,
            symbol=symbol,
            direction="hold",
            confidence=0.0,
            reason="base strategy has no signal",
        )

