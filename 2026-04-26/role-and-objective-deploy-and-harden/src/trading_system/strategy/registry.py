from __future__ import annotations

from dataclasses import dataclass, field

from trading_system.strategy.base import Strategy
from trading_system.strategy.families import DEFAULT_STRATEGIES


@dataclass
class StrategyRegistry:
    strategies: dict[str, Strategy] = field(default_factory=dict)

    def register(self, strategy: Strategy) -> None:
        if strategy.name in self.strategies:
            raise ValueError(f"duplicate strategy: {strategy.name}")
        self.strategies[strategy.name] = strategy

    def get(self, name: str) -> Strategy:
        return self.strategies[name]

    def names(self) -> list[str]:
        return sorted(self.strategies)


def default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for strategy_type in DEFAULT_STRATEGIES:
        registry.register(strategy_type())
    return registry

