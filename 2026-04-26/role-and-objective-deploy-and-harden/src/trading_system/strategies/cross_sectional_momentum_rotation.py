from __future__ import annotations

from trading_system.strategies._common import (
    StrategyRiskProfile,
    data_stale,
    float_value,
    market_closed,
    moving_average,
    percent_change,
    series_from_features,
)
from trading_system.strategy.base import Strategy, StrategySignal


class CrossSectionalMomentumRotationV1(Strategy):
    name = "cross_sectional_momentum_rotation_v1"
    family = "rotation"
    description = (
        "Cross-sectional ranking of liquid symbols with momentum, liquidity, and spread filters."
    )
    universe = ("SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC")
    required_data = (
        "symbol_rank_percentile",
        "close_prices",
        "benchmark_prices",
        "spread_pct",
        "volume",
        "average_volume",
        "market_regime",
        "market_is_open",
        "data_stale",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        "top_percentile_entry": 0.10,
        "top_percentile_hold": 0.30,
        "max_spread_pct": 0.40,
        "min_relative_volume": 1.15,
        "min_rank_score": 0.0,
        "max_holding_minutes": 7_200,
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=25.0,
        max_order_notional_usd=25.0,
        max_trades_per_day=3,
        max_open_positions=3,
        max_daily_loss_usd=25.0,
        stop_loss_pct=0.05,
        max_holding_minutes=7_200,
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
            return StrategySignal(self.name, symbol, "hold", 0.0, "signal suppressed: market closed"), "market closed"

        spread_pct = float_value(features.get("spread_pct"), default=0.0) * 100.0
        if spread_pct > self.config_schema["max_spread_pct"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "spread filter blocked signal"), "spread suppression"

        closes = series_from_features(features, "close_prices")
        if len(closes) < 126:
            return StrategySignal(self.name, symbol, "hold", 0.0, "insufficient price history"), "insufficient history"

        in_position = bool(features.get("in_position", False))
        market_regime = str(features.get("market_regime", "risk_on")).strip().lower()
        if market_regime in {"risk-off", "risk_off", "riskoff", "crisis"}:
            return StrategySignal(self.name, symbol, "exit", 0.96, "risk-off regime suppression"), "risk-off regime"

        rank_percentile = float_value(features.get("symbol_rank_percentile"), default=1.0)
        rel_volume = float_value(features.get("relative_volume"), default=0.0)
        if rel_volume <= 0.0:
            volume = float_value(features.get("volume"), default=0.0)
            avg_volume = float_value(features.get("average_volume"), default=0.0)
            rel_volume = (volume / avg_volume) if avg_volume > 0 else 0.0

        if rel_volume < self.config_schema["min_relative_volume"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "liquidity filter failed"), "liquidity filter"

        benchmark = series_from_features(features, "benchmark_prices")
        if benchmark:
            asset_return = percent_change(benchmark[-62], closes[-1], default=0.0) if len(benchmark) >= 62 else 0.0
        else:
            asset_return = 0.0
        if asset_return < self.config_schema["min_rank_score"]:
            return StrategySignal(self.name, symbol, "hold", 0.0, "weak baseline momentum"), "weak momentum"

        rank_entry = self.config_schema["top_percentile_entry"]
        rank_hold = self.config_schema["top_percentile_hold"]

        if in_position:
            if rank_percentile <= rank_hold:
                return StrategySignal(self.name, symbol, "hold", 0.0, "rank remains above maintenance threshold"), "holding"
            return StrategySignal(self.name, symbol, "exit", 0.88, "rank fell below maintenance threshold"), "rotation exit"

        if rank_percentile <= rank_entry and rel_volume >= self.config_schema["min_relative_volume"]:
            reason = f"rank={rank_percentile:.3f} in top {rank_entry:.2f}"
            confidence = min(1.0, 0.45 + (rank_entry - rank_percentile) / max(rank_entry, 1e-9) / 2.0)
            return StrategySignal(self.name, symbol, "buy", confidence, reason), reason

        return StrategySignal(self.name, symbol, "hold", 0.0, "symbol not in top cross-sectional set"), "not selected"
