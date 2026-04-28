from __future__ import annotations

from dataclasses import dataclass

from trading_system.strategy.base import StrategyMetrics


@dataclass(frozen=True)
class WalkForwardResult:
    strategy_name: str
    passed: bool
    periods_tested: int
    reason: str


def evaluate_walk_forward(metrics: StrategyMetrics, periods_tested: int) -> WalkForwardResult:
    passed = periods_tested >= 3 and metrics.regime_robustness >= 0.7 and metrics.max_drawdown <= 20
    reason = "passed walk-forward thresholds" if passed else "failed walk-forward thresholds"
    return WalkForwardResult(metrics.name, passed, periods_tested, reason)

