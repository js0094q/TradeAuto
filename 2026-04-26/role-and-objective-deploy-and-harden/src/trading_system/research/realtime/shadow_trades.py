from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowTrade:
    symbol: str
    strategy: str
    theoretical_entry_price: float
    theoretical_exit_price: float | None = None
    quantity: float = 1.0
    side: str = "long"
    estimated_slippage: float = 0.0
    suppressed: bool = False
    suppression_reason: str | None = None

    def realized_result(self) -> float | None:
        if self.theoretical_exit_price is None:
            return None
        direction = 1.0 if self.side == "long" else -1.0
        return ((self.theoretical_exit_price - self.theoretical_entry_price) * self.quantity * direction) - self.estimated_slippage

