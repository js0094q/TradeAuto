from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidityCheck:
    symbol: str
    passes: bool
    reasons: tuple[str, ...]


def evaluate_liquidity(
    symbol: str,
    *,
    dollar_volume: float,
    spread_pct: float,
    min_dollar_volume: float,
    max_spread_pct: float,
) -> LiquidityCheck:
    reasons: list[str] = []
    if dollar_volume < min_dollar_volume:
        reasons.append("dollar volume below minimum")
    if spread_pct > max_spread_pct:
        reasons.append("spread above maximum")
    return LiquidityCheck(symbol=symbol, passes=not reasons, reasons=tuple(reasons))

