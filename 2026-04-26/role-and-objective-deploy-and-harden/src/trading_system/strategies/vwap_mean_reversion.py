from __future__ import annotations

from trading_system.strategies._common import StrategyRiskProfile, data_stale, float_value, market_closed
from trading_system.strategy.base import Strategy, StrategySignal


class VwapMeanReversionV1(Strategy):
    name = "vwap_mean_reversion_v1"
    family = "mean_reversion"
    description = "VWAP mean reversion in liquid index ETFs with trend suppression and spread checks."
    universe = ("SPY", "QQQ", "IWM")
    required_data = (
        "close",
        "vwap",
        "z_score",
        "spread_pct",
        "trend_day",
        "volatility",
        "market_regime",
        "market_is_open",
        "data_stale",
        "in_position",
        "entry_time_minute",
        "minutes_since_entry",
        "position_minutes",
        "position_volume",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        "z_score_entry": 1.6,
        "z_score_exit": 0.0,
        "max_spread_pct": 0.30,
        "max_volatility_pct": 4.5,
        "max_holding_minutes": 360,
        "trend_day_ban": True,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=25.0,
        max_order_notional_usd=25.0,
        max_trades_per_day=2,
        max_open_positions=1,
        max_daily_loss_usd=25.0,
        stop_loss_pct=0.035,
        max_holding_minutes=360,
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
            return StrategySignal(self.name, symbol, "hold", 0.0, "spread filter blocked signal"), "spread filter"

        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff"}:
            return StrategySignal(self.name, symbol, "hold", 0.0, "risk regime suppression"), "risk-off regime"

        trend_day = bool(features.get("trend_day", False))
        if trend_day and self.config_schema["trend_day_ban"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "trend-day suppression"), "trend-day suppression"

        vol = float_value(features.get("volatility"), default=0.0)
        if vol > self.config_schema["max_volatility_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "volatility filter blocked signal"), "volatility filter"

        close = float_value(features.get("close"), default=0.0)
        vwap = float_value(features.get("vwap"), default=0.0)
        z_score = float_value(features.get("z_score"), default=0.0)
        if close <= 0 or vwap <= 0:
            return StrategySignal(self.name, symbol, "hold", 0.0, "missing vwap context"), "missing vwap"

        in_position = bool(features.get("in_position", False))
        minutes = int(float_value(features.get("minutes_since_entry"), default=0))

        if in_position:
            if close >= vwap:
                return StrategySignal(self.name, symbol, "exit", 0.95, "returned to VWAP"), "vwap reversion"
            if z_score <= self.config_schema["z_score_exit"]:
                return StrategySignal(self.name, symbol, "exit", 0.85, "z-score mean recovered"), "zscore recovery"
            if minutes >= self.config_schema["max_holding_minutes"]:
                return StrategySignal(self.name, symbol, "exit", 0.90, "time stop reached"), "time stop"
            return StrategySignal(self.name, symbol, "hold", 0.0, "mean reversion position active"), "holding"

        deviation = (vwap - close) / vwap
        if deviation >= 0 and z_score >= self.config_schema["z_score_entry"]:
            reason = f"price below VWAP by {deviation * 100:.2f}% with z-score {z_score:.2f}"
            return (
                StrategySignal(
                    self.name,
                    symbol,
                    "buy",
                    min(1.0, 0.5 + deviation * 2.0),
                    reason,
                ),
                "buy: " + reason,
            )

        return StrategySignal(self.name, symbol, "hold", 0.0, "reversion entry not met"), "no entry"
