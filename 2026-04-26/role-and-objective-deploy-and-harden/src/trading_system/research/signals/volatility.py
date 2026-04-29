from __future__ import annotations

from collections.abc import Sequence

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, mean, require_length, safe_divide


ATR_BREAKOUT = SignalMetadata(
    name="atr_breakout",
    category="volatility",
    description="Detects current close extension beyond prior close using prior ATR only.",
    required_inputs=("high_prices", "low_prices", "close_prices"),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate upside range expansion; negative values indicate downside expansion.",
    known_failure_modes=("gap reversals", "news whipsaws", "low-liquidity bars"),
    roles=("entry", "confirmation", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)

COMPRESSION_RATIO = SignalMetadata(
    name="compression_ratio",
    category="volatility",
    description="Compares short recent range to longer trailing range to find contraction before expansion.",
    required_inputs=("ranges",),
    output_range=(0.0, 1.0),
    interpretation="Lower values indicate tighter compression.",
    known_failure_modes=("quiet markets can stay quiet", "range data distorted by bad highs/lows"),
    roles=("confirmation", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)


def true_ranges(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> list[float]:
    require_length(highs, 2, "true_ranges highs")
    require_length(lows, 2, "true_ranges lows")
    require_length(closes, 2, "true_ranges closes")
    count = min(len(highs), len(lows), len(closes))
    ranges: list[float] = []
    for index in range(1, count):
        high = highs[index]
        low = lows[index]
        previous_close = closes[index - 1]
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return ranges


def atr_breakout(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    window: int = 14,
    multiplier: float = 1.0,
) -> SignalResult:
    ranges = true_ranges(highs, lows, closes)
    require_length(ranges, window + 1, "atr_breakout")
    prior_atr = mean(ranges[-window - 1 : -1])
    move = closes[-1] - closes[-2]
    value = clamp(safe_divide(move, prior_atr * multiplier))
    return SignalResult(
        ATR_BREAKOUT.name,
        value,
        "upside volatility expansion" if value > 0.25 else "downside volatility expansion" if value < -0.25 else "no breakout",
        ATR_BREAKOUT,
        inputs_used={"prior_atr": prior_atr, "move": move},
    )


def compression_ratio(ranges: Sequence[float], *, short_window: int = 5, long_window: int = 20) -> SignalResult:
    if short_window <= 0 or long_window <= 0 or short_window >= long_window:
        raise ValueError("short_window must be positive and smaller than long_window")
    require_length(ranges, long_window, "compression_ratio")
    short_range = mean(ranges[-short_window:])
    long_range = mean(ranges[-long_window:])
    ratio = max(0.0, safe_divide(short_range, long_range))
    value = min(1.0, ratio)
    return SignalResult(
        COMPRESSION_RATIO.name,
        value,
        "compressed" if value < 0.60 else "normal or expanded",
        COMPRESSION_RATIO,
        inputs_used={"short_range": short_range, "long_range": long_range},
    )

