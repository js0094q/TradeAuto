from __future__ import annotations

from trading_system.strategies._common import StrategyRiskProfile, data_stale, float_value, market_closed
from trading_system.strategy.base import Strategy, StrategySignal


class PostEarningsDriftV1(Strategy):
    name = "post_earnings_drift_v1"
    family = "event_driven"
    description = "Long-only post-earnings drift candidate using earnings surprise and drift confirmation."
    universe = ("AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "JPM", "UNH", "LLY")
    required_data = (
        "earnings_surprise",
        "post_earnings_gap",
        "post_earnings_volume_ratio",
        "window_days_since_earnings",
        "market_regime",
        "spread_pct",
        "market_is_open",
        "data_stale",
    )
    mode_support = {"shadow": True, "paper": False, "restricted_live": False}
    config_schema = {
        "min_positive_surprise": 0.01,
        "min_gap": 0.01,
        "min_volume_ratio": 1.20,
        "max_window_days": 30,
        "max_holding_days": 20,
        "max_spread_pct": 0.35,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=25.0,
        max_order_notional_usd=25.0,
        max_trades_per_day=1,
        max_open_positions=1,
        max_daily_loss_usd=25.0,
        stop_loss_pct=0.05,
        max_holding_minutes=13_000,
        allow_short=False,
    )
    default_enabled = False
    earnings_data_available = False

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
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: stale market data"), "stale"
        if market_closed(features):
            return StrategySignal(self.name, symbol, "hold", 0.0, "market closed"), "closed"

        if not bool(features.get("earnings_data_available", self.earnings_data_available)):
            return (
                StrategySignal(self.name, symbol, "hold", 0.0, "research-only: no earnings dataset for live/paper confirmation"),
                "missing earnings fields",
            )

        spread_pct = float_value(features.get("spread_pct"), default=0.0) * 100.0
        if spread_pct > self.config_schema["max_spread_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "spread filter blocked signal"), "spread filter"

        earnings_gap = float_value(features.get("post_earnings_gap"), default=0.0)
        surprise = float_value(features.get("earnings_surprise"), default=0.0)
        volume_ratio = float_value(features.get("post_earnings_volume_ratio"), default=0.0)
        days_since = int(float_value(features.get("window_days_since_earnings"), default=999))
        in_position = bool(features.get("in_position", False))
        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff"}:
            return StrategySignal(self.name, symbol, "hold", 0.0, "risk regime suppression"), "risk-off regime"

        if in_position:
            holding_days = int(float_value(features.get("position_days"), default=0))
            if days_since >= self.config_schema["max_window_days"]:
                return StrategySignal(self.name, symbol, "exit", 0.85, "post-earnings holding window complete"), "time stop"
            if surprise <= 0:
                return StrategySignal(self.name, symbol, "exit", 0.9, "earnings surprise deteriorated"), "earnings deterioration"
            if holding_days >= self.config_schema["max_holding_days"]:
                return StrategySignal(self.name, symbol, "exit", 0.9, "max holding window reached"), "holding limit"
            return StrategySignal(self.name, symbol, "hold", 0.0, "post-earnings drift position active"), "holding"

        if days_since > self.config_schema["max_window_days"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "outside post-earnings window"), "outside window"

        if surprise < self.config_schema["min_positive_surprise"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "earnings surprise not positive"), "surprise filter"
        if earnings_gap < self.config_schema["min_gap"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "post-earnings gap too small"), "gap filter"
        if volume_ratio < self.config_schema["min_volume_ratio"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "post-earnings volume did not confirm"), "volume filter"

        reason = f"positive surprise={surprise:.2f}, gap={earnings_gap:.2f}, volume ratio={volume_ratio:.2f}"
        return StrategySignal(self.name, symbol, "buy", min(1.0, 0.4 + surprise * 5), reason), reason
