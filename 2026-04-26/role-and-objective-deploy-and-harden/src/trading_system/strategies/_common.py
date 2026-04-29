from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Sequence


@dataclass(frozen=True)
class StrategyRiskProfile:
    max_position_notional_usd: float
    max_order_notional_usd: float
    max_trades_per_day: int
    max_open_positions: int
    max_daily_loss_usd: float
    allow_short: bool = False
    stop_loss_pct: float | None = None
    max_holding_minutes: int | None = None
    weekend_enabled: bool = True


def float_value(value: object, *, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def series_from_features(features: dict[str, object], key: str) -> list[float]:
    raw = features.get(key)
    if not isinstance(raw, Sequence):
        return []
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool):
            return []
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            return []
    return values


def percent_change(previous: float, current: float, *, default: float = 0.0) -> float:
    if previous in (0.0, 0) or previous is None:
        return default
    return (current - previous) / previous


def moving_average(values: Sequence[float], window: int) -> float:
    if window <= 0 or len(values) < window:
        return 0.0
    return fmean(values[-window:])


def realized_volatility(values: Sequence[float], window: int) -> float:
    if len(values) < max(2, window + 1):
        return 0.0
    pct_changes = [percent_change(values[i - 1], values[i]) for i in range(1, len(values))]
    if len(pct_changes) < window:
        return 0.0
    subset = pct_changes[-window:]
    if len(subset) < 2:
        return 0.0
    return pstdev(subset) * 100.0


def data_stale(features: dict[str, object]) -> bool:
    return bool(
        features.get("data_stale")
        or features.get("stale_data")
        or features.get("is_stale")
        or features.get("market_data_stale")
    )


def market_closed(features: dict[str, object]) -> bool:
    return bool(
        features.get("market_is_open") is False
        or features.get("market_closed")
        or features.get("session", "").strip().lower() == "closed"
    )


def spread_bad(features: dict[str, object], *, max_spread_pct: float) -> bool:
    spread = float_value(features.get("spread_pct"), default=0.0) * 100.0
    return spread > max_spread_pct

