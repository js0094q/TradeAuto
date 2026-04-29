from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


IntentMode = Literal["backtest", "paper", "paper_shadow", "live"]
IntentSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class OrderIntent:
    strategy_name: str
    symbol: str
    side: IntentSide
    target_weight: float
    quantity: float | None
    notional: float | None
    reason: str
    risk_approved: bool = False
    risk_blocks: tuple[str, ...] = ()
    mode: IntentMode = "paper"

    def with_risk_decision(self, *, approved: bool, blocks: tuple[str, ...]) -> OrderIntent:
        return replace(self, risk_approved=approved, risk_blocks=blocks)

    @property
    def adds_risk(self) -> bool:
        return self.side == "buy" and self.target_weight > 0.0
