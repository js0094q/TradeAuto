from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from trading_system.research.signals.base import mean, pct_change, require_length


class RegimeLabel(StrEnum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    HIGH_VOLATILITY = "high_volatility"
    MIXED = "mixed"


@dataclass(frozen=True)
class RegimeState:
    label: RegimeLabel
    score: float
    reasons: tuple[str, ...]
    no_trade_rules: tuple[str, ...]
    sizing_adjustment: float


def classify_market_regime(
    spy_prices: Sequence[float],
    qqq_prices: Sequence[float],
    *,
    realized_volatility_pct: float,
    iwm_relative_strength: float = 0.0,
    gap_pct: float = 0.0,
    short_window: int = 20,
    long_window: int = 50,
) -> RegimeState:
    require_length(spy_prices, long_window, "regime SPY prices")
    require_length(qqq_prices, long_window, "regime QQQ prices")
    spy_trend = pct_change(mean(spy_prices[-long_window:]), mean(spy_prices[-short_window:]))
    qqq_trend = pct_change(mean(qqq_prices[-long_window:]), mean(qqq_prices[-short_window:]))
    score = (spy_trend + qqq_trend + iwm_relative_strength) - (realized_volatility_pct / 100.0) - abs(gap_pct)
    reasons: list[str] = []
    no_trade: list[str] = []
    sizing = 1.0
    if realized_volatility_pct >= 35:
        label = RegimeLabel.HIGH_VOLATILITY
        reasons.append("realized volatility above stress threshold")
        no_trade.append("disable breakout entries without spread and volatility confirmation")
        sizing = 0.25
    elif score > 0.02:
        label = RegimeLabel.RISK_ON
        reasons.append("index trends and relative strength are constructive")
    elif score < -0.02:
        label = RegimeLabel.RISK_OFF
        reasons.append("index trends or volatility are unfavorable")
        no_trade.append("suppress long momentum without explicit trend confirmation")
        sizing = 0.50
    else:
        label = RegimeLabel.MIXED
        reasons.append("trend, breadth, and volatility are mixed")
        no_trade.append("avoid low-conviction signals")
        sizing = 0.75
    if abs(gap_pct) >= 0.02:
        no_trade.append("avoid opening-minute entries after large gap")
    return RegimeState(label=label, score=score, reasons=tuple(reasons), no_trade_rules=tuple(no_trade), sizing_adjustment=sizing)

