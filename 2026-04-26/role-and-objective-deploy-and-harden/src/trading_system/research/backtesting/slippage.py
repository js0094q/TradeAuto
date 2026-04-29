from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlippageAssumptions:
    spread_bps: float = 1.0
    slippage_bps: float = 1.0
    latency_bps: float = 0.0
    rejected_fill_rate: float = 0.0

    @property
    def total_bps(self) -> float:
        return self.spread_bps + self.slippage_bps + self.latency_bps


def adjusted_fill_price(price: float, *, side: str, assumptions: SlippageAssumptions) -> float:
    direction = 1.0 if side.lower() in {"buy", "cover"} else -1.0
    return price * (1.0 + direction * assumptions.total_bps / 10_000.0)


def slippage_penalty(notional: float, assumptions: SlippageAssumptions) -> float:
    return abs(notional) * assumptions.total_bps / 10_000.0

