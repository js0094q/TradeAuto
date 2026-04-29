from __future__ import annotations

from dataclasses import dataclass

from trading_system.research.signals.liquidity import spread_quality


@dataclass(frozen=True)
class SpreadSample:
    symbol: str
    bid: float
    ask: float
    spread_pct: float
    acceptable: bool
    reason: str | None = None


def evaluate_spread(symbol: str, bid: float, ask: float, *, max_spread_pct: float = 0.25) -> SpreadSample:
    result = spread_quality(bid, ask, max_spread_pct=max_spread_pct)
    spread_pct = float(result.inputs_used.get("spread_pct", 0.0))
    return SpreadSample(symbol=symbol, bid=bid, ask=ask, spread_pct=spread_pct, acceptable=not result.suppressed, reason=result.suppression_reason)

