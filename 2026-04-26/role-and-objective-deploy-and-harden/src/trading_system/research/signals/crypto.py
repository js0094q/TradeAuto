from __future__ import annotations

from collections.abc import Sequence

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, pct_change, require_length


CRYPTO_24_7_TREND = SignalMetadata(
    name="crypto_24_7_trend",
    category="crypto",
    description="Measures crypto trend with explicit 24/7 and weekend-liquidity assumptions.",
    required_inputs=("close_prices", "spread_pct"),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate trailing crypto trend persistence after liquidity suppression.",
    known_failure_modes=("weekend liquidity gaps", "exchange-specific outages", "high-volatility liquidation cascades"),
    roles=("entry", "confirmation", "suppression"),
    asset_classes=("crypto",),
)


def crypto_24_7_trend(
    prices: Sequence[float],
    *,
    window: int = 24,
    spread_pct: float = 0.0,
    max_spread_pct: float = 0.50,
    weekend: bool = False,
) -> SignalResult:
    require_length(prices, window + 1, "crypto_24_7_trend")
    momentum = pct_change(prices[-window - 1], prices[-1])
    penalty = 0.50 if weekend else 1.0
    value = clamp(momentum * 5.0 * penalty)
    suppression = None
    if spread_pct > max_spread_pct:
        suppression = "crypto spread above maximum"
        value = 0.0
    return SignalResult(
        CRYPTO_24_7_TREND.name,
        value,
        "crypto trend persists" if value > 0 else "crypto trend weak or suppressed",
        CRYPTO_24_7_TREND,
        suppression_reason=suppression,
        inputs_used={"momentum": momentum, "weekend": str(weekend), "spread_pct": spread_pct},
    )

