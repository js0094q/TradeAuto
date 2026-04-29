from __future__ import annotations

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, safe_divide


SPREAD_QUALITY = SignalMetadata(
    name="spread_quality",
    category="liquidity",
    description="Scores bid/ask spread quality and suppresses zero or crossed quotes.",
    required_inputs=("bid", "ask"),
    output_range=(0.0, 1.0),
    interpretation="One is tight and liquid; zero is untradable or too wide.",
    known_failure_modes=("stale quotes", "odd-lot display issues", "after-hours quote gaps"),
    roles=("confirmation", "suppression"),
    asset_classes=("equity", "etf", "option", "crypto"),
)

RELATIVE_VOLUME = SignalMetadata(
    name="relative_volume",
    category="liquidity",
    description="Compares current volume to a trailing average volume baseline.",
    required_inputs=("current_volume", "average_volume"),
    output_range=(0.0, 1.0),
    interpretation="Higher values indicate stronger volume confirmation.",
    known_failure_modes=("opening auction distortion", "corporate-action adjusted volume", "bad average baseline"),
    roles=("confirmation", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)


def spread_quality(bid: float, ask: float, *, max_spread_pct: float = 0.25) -> SignalResult:
    if bid <= 0 or ask <= 0 or ask < bid:
        return SignalResult(
            SPREAD_QUALITY.name,
            0.0,
            "invalid quote",
            SPREAD_QUALITY,
            suppression_reason="invalid, zero, or crossed quote",
            inputs_used={"bid": bid, "ask": ask},
        )
    mid = (bid + ask) / 2.0
    spread_pct = safe_divide(ask - bid, mid) * 100.0
    value = clamp(1.0 - safe_divide(spread_pct, max_spread_pct), 0.0, 1.0)
    suppression = "spread above maximum" if spread_pct > max_spread_pct else None
    return SignalResult(
        SPREAD_QUALITY.name,
        value,
        "tight spread" if suppression is None else "wide spread",
        SPREAD_QUALITY,
        suppression_reason=suppression,
        inputs_used={"spread_pct": spread_pct, "mid": mid},
    )


def relative_volume(current_volume: float, average_volume: float, *, confirmation_threshold: float = 1.2) -> SignalResult:
    ratio = safe_divide(current_volume, average_volume)
    value = clamp(ratio / confirmation_threshold, 0.0, 1.0)
    return SignalResult(
        RELATIVE_VOLUME.name,
        value,
        "volume confirms" if ratio >= confirmation_threshold else "volume below confirmation threshold",
        RELATIVE_VOLUME,
        suppression_reason=None if ratio > 0 else "missing or zero volume",
        inputs_used={"relative_volume": ratio},
    )

