from __future__ import annotations

from collections.abc import Sequence

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, mean, pct_change, require_length, safe_divide


RATE_OF_CHANGE = SignalMetadata(
    name="rate_of_change",
    category="momentum",
    description="Measures trailing price change over a fixed lookback without using future bars.",
    required_inputs=("close_prices",),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate recent upside momentum.",
    known_failure_modes=("gap exhaustion", "news reversals", "crowded momentum unwinds"),
    roles=("entry", "confirmation", "exit"),
    asset_classes=("equity", "etf", "crypto"),
)

RELATIVE_STRENGTH = SignalMetadata(
    name="relative_strength",
    category="momentum",
    description="Compares asset return to benchmark return over matching trailing windows.",
    required_inputs=("asset_prices", "benchmark_prices"),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate the asset is outperforming its benchmark.",
    known_failure_modes=("sector rotation", "benchmark mismatch", "short-lived single-name events"),
    roles=("confirmation", "suppression"),
    asset_classes=("equity", "etf"),
)

VOLUME_CONFIRMED_MOMENTUM = SignalMetadata(
    name="volume_confirmed_momentum",
    category="momentum",
    description="Combines trailing price momentum with relative volume confirmation.",
    required_inputs=("close_prices", "volumes"),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate momentum confirmed by elevated volume.",
    known_failure_modes=("opening auction distortion", "single-print volume spikes", "late-stage exhaustion"),
    roles=("entry", "confirmation"),
    asset_classes=("equity", "etf", "crypto"),
)


def rate_of_change(prices: Sequence[float], *, window: int = 20) -> SignalResult:
    require_length(prices, window + 1, "rate_of_change")
    value = clamp(pct_change(prices[-window - 1], prices[-1]) * 5.0)
    return SignalResult(
        RATE_OF_CHANGE.name,
        value,
        "positive momentum" if value > 0 else "negative momentum" if value < 0 else "flat momentum",
        RATE_OF_CHANGE,
        inputs_used={"window": window, "start": prices[-window - 1], "end": prices[-1]},
    )


def relative_strength(asset_prices: Sequence[float], benchmark_prices: Sequence[float], *, window: int = 20) -> SignalResult:
    require_length(asset_prices, window + 1, "relative_strength asset")
    require_length(benchmark_prices, window + 1, "relative_strength benchmark")
    asset_return = pct_change(asset_prices[-window - 1], asset_prices[-1])
    benchmark_return = pct_change(benchmark_prices[-window - 1], benchmark_prices[-1])
    value = clamp((asset_return - benchmark_return) * 5.0)
    return SignalResult(
        RELATIVE_STRENGTH.name,
        value,
        "outperforming benchmark" if value > 0 else "underperforming benchmark" if value < 0 else "in line with benchmark",
        RELATIVE_STRENGTH,
        inputs_used={"asset_return": asset_return, "benchmark_return": benchmark_return},
    )


def volume_confirmed_momentum(
    prices: Sequence[float],
    volumes: Sequence[float],
    *,
    price_window: int = 10,
    volume_window: int = 20,
) -> SignalResult:
    require_length(prices, price_window + 1, "volume_confirmed_momentum prices")
    require_length(volumes, volume_window, "volume_confirmed_momentum volumes")
    price_momentum = pct_change(prices[-price_window - 1], prices[-1])
    average_volume = mean(volumes[-volume_window:])
    relative_volume = safe_divide(volumes[-1], average_volume)
    value = clamp(price_momentum * min(relative_volume, 3.0) * 4.0)
    return SignalResult(
        VOLUME_CONFIRMED_MOMENTUM.name,
        value,
        "volume confirms move" if relative_volume >= 1.2 else "volume does not confirm move",
        VOLUME_CONFIRMED_MOMENTUM,
        inputs_used={"price_momentum": price_momentum, "relative_volume": relative_volume},
    )

