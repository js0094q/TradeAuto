from __future__ import annotations

from dataclasses import dataclass

from trading_system.strategy.base import StrategyMetrics


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class StrategyScore:
    name: str
    score: float
    components: dict[str, float]


def score_strategy(metrics: StrategyMetrics) -> StrategyScore:
    components = {
        "risk_adjusted_return": _clamp((metrics.sharpe * 12.0) + (metrics.sortino * 8.0)),
        "drawdown_control": _clamp(100.0 - (metrics.max_drawdown * 4.0)),
        "consistency": _clamp(metrics.win_rate * 100.0 + metrics.profit_factor * 10.0),
        "execution_quality": _clamp(metrics.execution_reliability * 100.0),
        "regime_fit": _clamp(metrics.regime_robustness * 100.0),
        "liquidity": _clamp(100.0 - metrics.spread_sensitivity * 20.0),
        "trade_frequency": _clamp(metrics.trade_frequency * 100.0),
        "live_readiness": _clamp(metrics.live_readiness * 100.0),
        "overfitting_penalty": _clamp(metrics.overfitting_penalty * 100.0),
        "slippage_penalty": _clamp(metrics.slippage_sensitivity * 20.0),
        "concentration_penalty": _clamp(metrics.concentration_penalty * 100.0),
    }
    positive = (
        components["risk_adjusted_return"] * 0.18
        + components["drawdown_control"] * 0.18
        + components["consistency"] * 0.12
        + components["execution_quality"] * 0.14
        + components["regime_fit"] * 0.12
        + components["liquidity"] * 0.08
        + components["trade_frequency"] * 0.06
        + components["live_readiness"] * 0.12
    )
    penalties = (
        components["overfitting_penalty"] * 0.15
        + components["slippage_penalty"] * 0.10
        + components["concentration_penalty"] * 0.10
    )
    return StrategyScore(metrics.name, _clamp(positive - penalties), components)


def rank_strategies(metrics: list[StrategyMetrics]) -> list[StrategyScore]:
    return sorted((score_strategy(item) for item in metrics), key=lambda item: item.score, reverse=True)

