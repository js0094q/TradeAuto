from __future__ import annotations

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, safe_divide
from trading_system.research.signals.liquidity import spread_quality


OPTIONS_LIQUIDITY = SignalMetadata(
    name="options_liquidity_score",
    category="options",
    description="Scores options volume, open interest, and spread quality for confirmation or suppression only.",
    required_inputs=("volume", "open_interest", "bid", "ask"),
    output_range=(0.0, 1.0),
    interpretation="Higher values indicate options data is liquid enough to inform equity confirmation.",
    known_failure_modes=("stale option quotes", "wide spreads", "earnings IV distortion", "thin strikes"),
    roles=("confirmation", "suppression"),
    asset_classes=("option", "equity"),
)

IV_RANK = SignalMetadata(
    name="iv_rank",
    category="options",
    description="Places current implied volatility inside its trailing observed range.",
    required_inputs=("current_iv", "iv_low", "iv_high"),
    output_range=(0.0, 1.0),
    interpretation="Higher values indicate current IV is elevated versus its range.",
    known_failure_modes=("short IV history", "regime breaks", "earnings windows"),
    roles=("confirmation", "suppression"),
    asset_classes=("option", "equity"),
)


def options_liquidity_score(
    *,
    volume: float,
    open_interest: float,
    bid: float,
    ask: float,
    min_volume: float = 500.0,
    min_open_interest: float = 1_000.0,
    max_spread_pct: float = 10.0,
) -> SignalResult:
    quote = spread_quality(bid, ask, max_spread_pct=max_spread_pct)
    volume_score = clamp(safe_divide(volume, min_volume), 0.0, 1.0)
    oi_score = clamp(safe_divide(open_interest, min_open_interest), 0.0, 1.0)
    value = min(quote.value, volume_score, oi_score)
    suppression = None
    if value < 0.70:
        suppression = "options liquidity below confirmation threshold"
    return SignalResult(
        OPTIONS_LIQUIDITY.name,
        value,
        "usable as equity confirmation" if suppression is None else "do not use options signal",
        OPTIONS_LIQUIDITY,
        suppression_reason=suppression,
        inputs_used={"volume_score": volume_score, "open_interest_score": oi_score, **dict(quote.inputs_used)},
    )


def iv_rank(*, current_iv: float, iv_low: float, iv_high: float) -> SignalResult:
    if iv_high <= iv_low:
        raise ValueError("iv_high must be greater than iv_low")
    value = clamp(safe_divide(current_iv - iv_low, iv_high - iv_low), 0.0, 1.0)
    return SignalResult(
        IV_RANK.name,
        value,
        "elevated IV" if value >= 0.70 else "low or normal IV",
        IV_RANK,
        inputs_used={"current_iv": current_iv, "iv_low": iv_low, "iv_high": iv_high},
    )

