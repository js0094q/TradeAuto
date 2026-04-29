from __future__ import annotations

from collections.abc import Sequence

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, mean, require_length, safe_divide


MOVING_AVERAGE_TREND = SignalMetadata(
    name="moving_average_trend",
    category="trend",
    description="Compares short and long moving averages using only observations available at evaluation time.",
    required_inputs=("close_prices",),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate short-term trend above long-term trend.",
    known_failure_modes=("whipsaw in sideways markets", "lag after gap reversals", "poor behavior during stale data"),
    roles=("entry", "confirmation", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)


def moving_average_trend(prices: Sequence[float], *, short_window: int = 20, long_window: int = 50) -> SignalResult:
    if short_window <= 0 or long_window <= 0 or short_window >= long_window:
        raise ValueError("short_window must be positive and smaller than long_window")
    require_length(prices, long_window, "moving_average_trend")
    short_ma = mean(prices[-short_window:])
    long_ma = mean(prices[-long_window:])
    raw = safe_divide(short_ma - long_ma, long_ma)
    value = clamp(raw * 10.0)
    if value > 0.10:
        interpretation = "bullish trend confirmation"
    elif value < -0.10:
        interpretation = "bearish or no-long suppression"
    else:
        interpretation = "trend is neutral or noisy"
    return SignalResult(
        name=MOVING_AVERAGE_TREND.name,
        value=value,
        interpretation=interpretation,
        metadata=MOVING_AVERAGE_TREND,
        inputs_used={"short_ma": short_ma, "long_ma": long_ma},
    )

