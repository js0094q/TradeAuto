from __future__ import annotations

from collections.abc import Sequence

from trading_system.research.signals.base import SignalMetadata, SignalResult, clamp, mean, require_length, safe_divide, z_score


ZSCORE_REVERSION = SignalMetadata(
    name="zscore_reversion",
    category="mean_reversion",
    description="Scores stretch from trailing mean; positive values favor long reversion after downside stretch.",
    required_inputs=("close_prices",),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate downside stretch; negative values indicate upside stretch.",
    known_failure_modes=("trend continuation", "crashes", "single-name catalysts", "illiquid prints"),
    roles=("entry", "exit", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)

RSI_STRETCH = SignalMetadata(
    name="rsi_stretch",
    category="mean_reversion",
    description="Uses trailing RSI stretch as an explainable overbought/oversold signal.",
    required_inputs=("close_prices",),
    output_range=(-1.0, 1.0),
    interpretation="Positive values indicate oversold stretch; negative values indicate overbought stretch.",
    known_failure_modes=("persistent trends", "earnings gaps", "macro shock days"),
    roles=("entry", "exit", "suppression"),
    asset_classes=("equity", "etf", "crypto"),
)


def zscore_reversion(prices: Sequence[float], *, window: int = 20) -> SignalResult:
    score = z_score(prices, window=window)
    value = clamp(-score / 3.0)
    return SignalResult(
        ZSCORE_REVERSION.name,
        value,
        "downside stretch" if value > 0 else "upside stretch" if value < 0 else "near mean",
        ZSCORE_REVERSION,
        inputs_used={"z_score": score, "window_mean": mean(prices[-window:])},
    )


def rsi_stretch(prices: Sequence[float], *, period: int = 14) -> SignalResult:
    require_length(prices, period + 1, "rsi_stretch")
    deltas = [prices[index] - prices[index - 1] for index in range(len(prices) - period, len(prices))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        rsi = 100.0
    else:
        rsi = 100.0 - (100.0 / (1.0 + safe_divide(avg_gain, avg_loss)))
    if rsi < 30:
        value = clamp((30.0 - rsi) / 30.0)
        interpretation = "oversold stretch"
    elif rsi > 70:
        value = clamp(-(rsi - 70.0) / 30.0)
        interpretation = "overbought stretch"
    else:
        value = 0.0
        interpretation = "no RSI stretch"
    return SignalResult(RSI_STRETCH.name, value, interpretation, RSI_STRETCH, inputs_used={"rsi": rsi})

