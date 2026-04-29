from __future__ import annotations

from trading_system.strategies._common import StrategyRiskProfile, data_stale
from trading_system.strategy.base import Strategy, StrategySignal


def _to_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class CryptoTrendBreakoutV1(Strategy):
    name = "crypto_trend_breakout_v1"
    family = "crypto_trend"
    description = "24/7 crypto trend breakout with weekend and volatility suppression."
    universe = ("BTC/USD", "ETH/USD")
    required_data = (
        "close_prices",
        "breakout_level",
        "atr_now",
        "atr_prior",
        "spread_pct",
        "is_weekend",
        "market_regime",
        "volatility",
        "data_stale",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        "atr_expansion_threshold": 1.10,
        "max_spread_pct": 0.80,
        "max_volatility_pct": 8.0,
        "min_trend_strength": 0.0,
        "max_holding_minutes": 600,
        "weekend_capital_risk": True,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=15.0,
        max_order_notional_usd=15.0,
        max_trades_per_day=2,
        max_open_positions=1,
        max_daily_loss_usd=15.0,
        stop_loss_pct=0.05,
        max_holding_minutes=600,
        allow_short=False,
        weekend_enabled=True,
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
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: stale data"), "stale data"

        spread_pct = _to_float(features.get("spread_pct"), default=0.0) * 100.0
        if spread_pct > self.config_schema["max_spread_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "spread too wide for entry"), "spread"

        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff"}:
            return StrategySignal(self.name, symbol, "hold", 0.0, "risk-off suppression"), "risk regime"

        closes = [
            _to_float(item)
            for item in features.get("close_prices", [])
            if isinstance(item, (int, float))
        ]
        if len(closes) < 25:
            return StrategySignal(self.name, symbol, "hold", 0.0, "insufficient crypto history"), "insufficient history"

        atr_now = _to_float(features.get("atr_now"), default=0.0)
        atr_prior = _to_float(features.get("atr_prior"), default=0.0)
        if atr_prior <= 0 or (atr_now / atr_prior) < self.config_schema["atr_expansion_threshold"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "ATR expansion missing"), "ATR filter"

        vol = _to_float(features.get("volatility"), default=0.0)
        if vol > self.config_schema["max_volatility_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "volatility spike suppression"), "volatility filter"

        if bool(features.get("is_weekend", False)) and self.config_schema["weekend_capital_risk"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "weekend risk filter"), "weekend filter"

        breakout_level = _to_float(features.get("breakout_level"), default=closes[-1])
        current = closes[-1]
        in_position = bool(features.get("in_position", False))
        if in_position:
            trailing_stop = _to_float(features.get("trailing_stop"), default=current * 0.95)
            if current <= trailing_stop:
                return StrategySignal(self.name, symbol, "exit", 0.95, "trailing stop triggered"), "stop"
            if int(_to_float(features.get("position_minutes"), default=0)) >= self.config_schema["max_holding_minutes"]:
                return StrategySignal(self.name, symbol, "exit", 0.9, "time stop"), "time stop"
            return StrategySignal(self.name, symbol, "hold", 0.0, "crypto breakout position active"), "holding"

        if current > breakout_level:
            trend_strength = (_to_float(features.get("trend_strength"), default=0.0))
            if trend_strength < self.config_schema["min_trend_strength"]:
                return StrategySignal(self.name, symbol, "hold", 0.0, "breakout trend too weak"), "weak trend"
            reason = f"price broke breakout level {breakout_level:.2f} with vol expansion"
            return StrategySignal(self.name, symbol, "buy", min(1.0, 0.6 + trend_strength * 0.02), reason), reason

        return StrategySignal(self.name, symbol, "hold", 0.0, "breakout level not crossed"), "waiting"

