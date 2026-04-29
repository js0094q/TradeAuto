from __future__ import annotations

from trading_system.strategy.base import Strategy
from trading_system.strategies import (
    CryptoTrendBreakoutV1,
    CrossSectionalMomentumRotationV1,
    EtfTimeSeriesMomentumV1,
    OpeningRangeBreakoutV1,
    PostEarningsDriftV1,
    VwapMeanReversionV1,
)


class MomentumContinuation(Strategy):
    name = "momentum_continuation"
    family = "momentum"
    description = "Continuation after strong movement with trend, breakout, volume, and regime confirmation."


class PullbackInUptrend(Strategy):
    name = "pullback_in_uptrend"
    family = "pullback"
    description = "Controlled pullback entries in assets above long-term trend with RSI reset."


class VolatilityCompressionBreakout(Strategy):
    name = "volatility_compression_breakout"
    family = "breakout"
    description = "Breakout after Bollinger/ATR/range compression with volume expansion."


class MeanReversion(Strategy):
    name = "mean_reversion"
    family = "mean_reversion"
    description = "Short-term overreaction entries in liquid assets outside strong downtrends."


class OpeningRangeBreakout(Strategy):
    name = "opening_range_breakout"
    family = "intraday_breakout"
    description = "Defined-window opening range breakouts with volume and trend confirmation."


class GapContinuationOrFade(Strategy):
    name = "gap_continuation_or_fade"
    family = "gap"
    description = "Gap behavior strategy using gap size, premarket volume, news, and first-hour confirmation."


class EtfRegimeStrategy(Strategy):
    name = "etf_regime_strategy"
    family = "regime"
    description = "Broad ETF trend and volatility regime filter controlling exposure."


class EarningsNewsAvoidanceLayer(Strategy):
    name = "earnings_news_avoidance"
    family = "risk_filter"
    description = "Avoids uncontrolled event risk from earnings, binary events, and illiquid news spikes."


DEFAULT_STRATEGIES: tuple[type[Strategy], ...] = (
    EtfTimeSeriesMomentumV1,
    CrossSectionalMomentumRotationV1,
    OpeningRangeBreakoutV1,
    VwapMeanReversionV1,
    PostEarningsDriftV1,
    CryptoTrendBreakoutV1,
    MomentumContinuation,
    PullbackInUptrend,
    VolatilityCompressionBreakout,
    MeanReversion,
    OpeningRangeBreakout,
    GapContinuationOrFade,
    EtfRegimeStrategy,
    EarningsNewsAvoidanceLayer,
)
