from __future__ import annotations

from statistics import pstdev

from trading_system.strategies._common import (
    StrategyRiskProfile,
    series_from_features,
    data_stale,
    float_value,
    market_closed,
    moving_average,
    percent_change,
)
from trading_system.strategy.base import Strategy, StrategySignal


class EtfTimeSeriesMomentumV1(Strategy):
    name = "etf_time_series_momentum_v1"
    family = "trend"
    description = (
        "Liquid-ETF time-series momentum using intermediate trend confirmation and realized-volatility "
        "filters."
    )
    universe = (
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLI",
        "XLY",
        "XLP",
        "XLU",
        "XLB",
        "XLRE",
        "XLC",
    )
    required_data = (
        "close_prices",
        "spread_pct",
        "market_regime",
        "market_is_open",
        "data_stale",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        "close_prices_window": 200,
        "return_20_window": 20,
        "return_60_window": 60,
        "volatility_window": 20,
        "max_spread_pct": 0.25,
        "max_realized_vol_pct": 6.0,
        "max_holding_minutes": 13_000,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=25.0,
        max_order_notional_usd=25.0,
        max_trades_per_day=3,
        max_open_positions=3,
        max_daily_loss_usd=25.0,
        stop_loss_pct=0.04,
        max_holding_minutes=13_000,
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
        reason = "ETF time-series momentum not triggered"
        if data_stale(features):
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: stale market data"), "stale data suppressed"
        if market_closed(features):
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: market closed"), "market closed"

        closes = series_from_features(features, "close_prices")
        if len(closes) < 205:
            return StrategySignal(self.name, symbol, "hold", 0.0, "insufficient history"), "insufficient history"

        spread_pct = float_value(features.get("spread_pct"), default=0.0) * 100.0
        if spread_pct > self.config_schema["max_spread_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "entry blocked by spread filter"), "spread suppression"

        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff", "defensive"}:
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed by risk-off regime"), "risk-off regime"

        current = closes[-1]
        return_20 = percent_change(closes[-21], current, default=0.0) * 100.0
        return_60 = percent_change(closes[-61], current, default=0.0) * 100.0
        sma_50 = moving_average(closes, 50)
        sma_200 = moving_average(closes, 200)

        window_changes = [percent_change(closes[idx - 1], closes[idx], default=0.0) for idx in range(1, len(closes))]
        volatility = pstdev(window_changes[-20:]) * 100.0 if len(window_changes) >= 20 else 0.0
        if volatility > self.config_schema["max_realized_vol_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "entry blocked by realized-volatility filter"), "volatility filter"

        in_position = bool(features.get("in_position", False))
        if in_position:
            minutes_in_position = int(float_value(features.get("minutes_since_entry"), default=self.config_schema["max_holding_minutes"]))
            exit_signal = False
            if current < sma_50:
                exit_signal = True
                reason = "close crossed below 50-day moving average"
            elif return_20 < 0.0:
                exit_signal = True
                reason = "20-day return turned negative"
            elif market_regime not in {"risk_on", "neutral"}:
                exit_signal = True
                reason = "risk regime deteriorated"
            elif minutes_in_position >= self.config_schema["max_holding_minutes"]:
                exit_signal = True
                reason = "max holding period elapsed"
            if exit_signal:
                return StrategySignal(self.name, symbol, "exit", 0.92, reason), reason
            return StrategySignal(self.name, symbol, "hold", 0.0, "trend and regime still valid"), "holding"

        if return_20 <= 0 or return_60 <= 0:
            return StrategySignal(self.name, symbol, "hold", 0.0, "returns not momentum-positive"), "returns filter"
        if current <= sma_50:
            return StrategySignal(self.name, symbol, "hold", 0.0, "price not above 50-day SMA"), "trend filter"
        if sma_50 <= sma_200:
            return StrategySignal(self.name, symbol, "hold", 0.0, "50-day SMA not above 200-day SMA"), "trend filter"

        reason = (
            f"20d={return_20:.2f}% and 60d={return_60:.2f}% returns with 50/200 SMA bullish alignment"
        )
        confidence = min(1.0, 0.5 + max(0.0, return_20) / 10.0 + max(0.0, return_60) / 15.0)
        return StrategySignal(self.name, symbol, "buy", confidence, reason), reason if for_explanation else reason
