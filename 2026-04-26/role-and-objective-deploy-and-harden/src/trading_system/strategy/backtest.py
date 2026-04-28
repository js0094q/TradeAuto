from __future__ import annotations

from dataclasses import dataclass

from trading_system.strategy.base import StrategyMetrics


@dataclass(frozen=True)
class BacktestResult:
    strategy_name: str
    passed: bool
    metrics: StrategyMetrics
    reason: str


def evaluate_backtest(metrics: StrategyMetrics) -> BacktestResult:
    passed = (
        metrics.out_of_sample_return > 0
        and metrics.max_drawdown <= 20
        and metrics.profit_factor >= 1.1
        and metrics.execution_reliability >= 0.95
    )
    reason = "passed backtest thresholds" if passed else "failed backtest thresholds"
    return BacktestResult(metrics.name, passed, metrics, reason)

