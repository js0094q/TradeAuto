from __future__ import annotations

from trading_system.strategies._common import (
    StrategyRiskProfile,
    data_stale,
    float_value,
    market_closed,
)
from trading_system.strategy.base import Strategy, StrategySignal


class OpeningRangeBreakoutV1(Strategy):
    name = "opening_range_breakout_v1"
    family = "intraday_breakout"
    description = (
        "Opening-range breakout with volume expansion, ATR confirmation, and risk-aware intraday exit rules."
    )
    universe = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META")
    required_data = (
        "opening_range_high",
        "opening_range_low",
        "high",
        "low",
        "close",
        "atr_now",
        "atr_prior",
        "spread_pct",
        "volume",
        "volume_baseline",
        "market_is_open",
        "minutes_since_open",
        "market_regime",
        "data_stale",
        "minute",
        "is_eod",
        "in_position",
        "entry_price",
        "position_minutes",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        "opening_range_minutes": [5, 15, 30],
        "relative_volume_threshold": 1.25,
        "atr_expansion_threshold": 1.08,
        "max_spread_pct": 0.35,
        "max_minutes_from_open": 1,
        "close_cutoff_minute": 900,
        "max_holding_minutes": 390,
        "max_open_positions": 1,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=25.0,
        max_order_notional_usd=25.0,
        max_trades_per_day=1,
        max_open_positions=1,
        max_daily_loss_usd=25.0,
        stop_loss_pct=0.02,
        max_holding_minutes=390,
        allow_short=False,
    )
    default_enabled = False

    def generate_signal(self, symbol: str, features: dict[str, float | int | bool | str | object]) -> StrategySignal:
        return self._generate(symbol, features, for_explanation=False)[0]

    def explain_signal(self, symbol: str, features: dict[str, float | int | bool | str | object]) -> str:
        return self._generate(symbol, features, for_explanation=True)[1]

    def _generate(
        self,
        symbol: str,
        features: dict[str, float | int | bool | str | object],
        *,
        for_explanation: bool = False,
    ) -> tuple[StrategySignal, str]:
        if data_stale(features):
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: stale market data"), "stale data"

        if market_closed(features):
            return StrategySignal(self.name, symbol, "hold", 0.0, "market closed"), "market closed"

        spread_pct = float_value(features.get("spread_pct"), default=0.0) * 100.0
        if spread_pct > self.config_schema["max_spread_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "spread filter suppression"), "spread filter"

        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff"}:
            return StrategySignal(self.name, symbol, "hold", 0.0, "risk regime suppression"), "risk-off regime"

        current_price = float_value(features.get("close"), default=0.0)
        open_high = float_value(features.get("opening_range_high"), default=0.0)
        if open_high <= 0 or current_price <= 0:
            return StrategySignal(self.name, symbol, "hold", 0.0, "missing opening-range context"), "missing opening range"

        atr_now = float_value(features.get("atr_now"), default=0.0)
        atr_prior = float_value(features.get("atr_prior"), default=0.0)
        if atr_prior <= 0 or (atr_now / atr_prior) < self.config_schema["atr_expansion_threshold"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "ATR expansion filter blocked signal"), "ATR filter"

        current_volume = float_value(features.get("volume"), default=0.0)
        volume_baseline = float_value(features.get("volume_baseline"), default=0.0)
        if volume_baseline <= 0 or (current_volume / volume_baseline) < self.config_schema["relative_volume_threshold"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "relative volume filter blocked signal"), "volume filter"

        minutes_since_open = int(float_value(features.get("minutes_since_open"), default=0))
        if minutes_since_open <= self.config_schema["max_minutes_from_open"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "within OR blackout window after open"), "time-of-open blacklist"

        in_position = bool(features.get("in_position", False))
        is_eod = bool(features.get("is_eod"))
        if is_eod:
            return StrategySignal(self.name, symbol, "exit", 0.98, "end-of-day exit rule"), "eod"

        if in_position:
            entry_price = float_value(features.get("entry_price"), default=current_price)
            stop = float_value(features.get("stop_level"), default=entry_price * (1.0 - self.risk_profile.stop_loss_pct))
            minute_age = int(float_value(features.get("position_minutes"), default=0))
            if minute_age >= self.config_schema["max_holding_minutes"]:
                return StrategySignal(self.name, symbol, "exit", 0.95, "time stop reached"), "max holding period"
            if current_price <= stop:
                return StrategySignal(self.name, symbol, "exit", 0.99, "ATR stop-loss triggered"), "stop"
            if float_value(features.get("close"), default=0.0) < float_value(features.get("vwap"), default=current_price):
                return StrategySignal(self.name, symbol, "exit", 0.8, "VWAP failure exit"), "vwap exit"
            return StrategySignal(self.name, symbol, "hold", 0.0, "breakout position active"), "holding"

        if current_price > open_high:
            reason = f"broke opening range high with ATR expansion {atr_now / atr_prior:.2f}x"
            confidence = min(1.0, 0.60 + (current_volume / max(volume_baseline, 1.0) - 1.25) / 3.0)
            return StrategySignal(self.name, symbol, "buy", confidence, reason), reason

        return StrategySignal(self.name, symbol, "hold", 0.0, "price did not clear opening range"), "waiting"

