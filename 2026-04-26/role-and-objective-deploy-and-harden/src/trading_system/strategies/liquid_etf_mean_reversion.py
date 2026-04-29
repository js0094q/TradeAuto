from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping, Sequence

from trading_system.strategies._common import StrategyRiskProfile
from trading_system.strategies.indicators import close_values, mean_reversion_z_score, relative_volume, sma, spread_bps
from trading_system.strategies.rebalance import RankingSnapshot, StrategyExit, StrategyRebalance, StrategySelection
from trading_system.strategies.strategy_config import StrategyConfig, default_liquid_etf_mean_reversion_config
from trading_system.strategy.base import Strategy, StrategySignal
from trading_system.trading.order_intents import OrderIntent


class LiquidEtfMeanReversionV1(Strategy):
    name = "liquid_etf_mean_reversion_v1"
    family = "mean_reversion"
    description = "Paper-shadow liquid ETF mean reversion using the tested positive-oversold z-score convention."
    universe = default_liquid_etf_mean_reversion_config().universe
    required_data = (
        "daily_bars_by_symbol",
        "quotes_by_symbol",
        "positions_by_symbol",
        "data_stale",
        "kill_switch_enabled",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = {
        **default_liquid_etf_mean_reversion_config().to_dict(),
        "mean_reversion": {
            "z_score_entry": 1.5,
            "sign_convention": "(5d_mean - close) / 20d_std; positive means oversold below mean",
        },
    }
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=7_500.0,
        max_order_notional_usd=7_500.0,
        max_trades_per_day=2,
        max_open_positions=2,
        max_daily_loss_usd=150.0,
        stop_loss_pct=0.03,
        max_holding_minutes=1_950,
        allow_short=False,
    )
    default_enabled = False
    z_score_entry = 1.5

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or default_liquid_etf_mean_reversion_config()

    def generate_signal(self, symbol: str, features: dict[str, object]) -> StrategySignal:
        bars_by_symbol = features.get("daily_bars_by_symbol")
        if not isinstance(bars_by_symbol, Mapping):
            return StrategySignal(self.name, symbol, "hold", 0.0, "missing daily bars")
        positions = features.get("positions_by_symbol")
        rebalance = self.rebalance(
            bars_by_symbol=bars_by_symbol,
            quotes_by_symbol=features.get("quotes_by_symbol") if isinstance(features.get("quotes_by_symbol"), Mapping) else None,
            positions_by_symbol=positions if isinstance(positions, Mapping) else None,
            mode=str(features.get("mode", self.config.mode)),
            kill_switch_enabled=bool(features.get("kill_switch_enabled", False)),
            data_stale=bool(features.get("data_stale", False)),
        )
        for selection in rebalance.selected:
            if selection.symbol == symbol:
                return StrategySignal(self.name, symbol, "buy", 0.70, selection.reason, target_weight=selection.target_weight, indicators=selection.indicators, timestamp=rebalance.timestamp, mode=rebalance.mode)
        for exit_item in rebalance.exits:
            if exit_item.symbol == symbol:
                return StrategySignal(self.name, symbol, "exit", 0.90, exit_item.reason, timestamp=rebalance.timestamp, mode=rebalance.mode)
        return StrategySignal(self.name, symbol, "hold", 0.0, "mean-reversion trigger not met", timestamp=rebalance.timestamp, mode=rebalance.mode)

    def rebalance(
        self,
        *,
        bars_by_symbol: Mapping[str, Sequence[object]],
        quotes_by_symbol: Mapping[str, object] | None = None,
        positions_by_symbol: Mapping[str, Mapping[str, object]] | None = None,
        mode: str | None = None,
        timestamp: datetime | None = None,
        kill_switch_enabled: bool = False,
        data_stale: bool = False,
        portfolio_value: float | None = None,
    ) -> StrategyRebalance:
        as_of = timestamp or datetime.now(UTC)
        run_mode = mode or self.config.mode
        quotes = quotes_by_symbol or {}
        positions = positions_by_symbol or {}
        current_positions = set(positions)
        risk_blocks: list[str] = []
        warnings: list[str] = []

        if not self.config.enabled:
            risk_blocks.append("strategy_disabled")
        if run_mode == "live":
            risk_blocks.append("live_orders_disabled")
        if data_stale:
            risk_blocks.append("stale_data")
        if kill_switch_enabled:
            risk_blocks.append("kill_switch_active")

        benchmark_bars = bars_by_symbol.get(self.config.regime.benchmark, ())
        benchmark_closes = close_values(benchmark_bars)
        benchmark_sma = sma(benchmark_closes, self.config.regime.sma_days)
        benchmark_close = benchmark_closes[-1] if benchmark_closes else None
        regime_ok = benchmark_close is not None and benchmark_sma is not None and benchmark_close > benchmark_sma
        if benchmark_close is None or benchmark_sma is None:
            risk_blocks.append("insufficient_benchmark_history")
        elif not regime_ok:
            risk_blocks.append("benchmark_regime_failed")

        ranking_rows: list[RankingSnapshot] = []
        entry_candidates: list[RankingSnapshot] = []
        exits: list[StrategyExit] = []

        for symbol in self.config.universe:
            bars = bars_by_symbol.get(symbol, ())
            closes = close_values(bars)
            close = closes[-1] if closes else None
            mean_5 = sma(closes, 5)
            symbol_sma = sma(closes, self.config.trend.sma_days)
            z_score = mean_reversion_z_score(closes, mean_window=5, z_window=self.config.ranking.lookback_days)
            rel_volume = relative_volume(bars, self.config.liquidity.relative_volume_days)
            quote_spread_bps = spread_bps(quotes.get(symbol))
            symbol_blocks: list[str] = []
            above_near_sma = close is not None and symbol_sma is not None and close > symbol_sma * 0.95

            if close is None or mean_5 is None or symbol_sma is None or z_score is None:
                symbol_blocks.append("insufficient_symbol_history")
            if close is not None and symbol_sma is not None and not above_near_sma:
                symbol_blocks.append("long_term_trend_guard_failed")
            if self.config.liquidity.require_relative_volume:
                if rel_volume is None:
                    symbol_blocks.append("relative_volume_unavailable")
                elif self.config.liquidity.min_relative_volume is not None and rel_volume < self.config.liquidity.min_relative_volume:
                    symbol_blocks.append("relative_volume_filter_failed")
            if self.config.liquidity.require_spread_filter:
                if quote_spread_bps is None:
                    symbol_blocks.append("spread_quote_unavailable")
                elif self.config.liquidity.max_spread_bps is not None and quote_spread_bps > self.config.liquidity.max_spread_bps:
                    symbol_blocks.append("spread_filter_failed")
            elif quote_spread_bps is None:
                warnings.append(f"{symbol}: spread quote unavailable")

            indicators = {
                "close": close,
                "mean_5": mean_5,
                "sma_200": symbol_sma,
                "z_score": z_score,
                "relative_volume_20d": rel_volume,
                "spread_bps": quote_spread_bps,
                "z_score_sign_convention": "positive_oversold_mean_5_minus_close",
            }
            row = RankingSnapshot(
                symbol=symbol,
                rank=0,
                return_60d=0.0 if z_score is None else z_score,
                above_sma_200=above_near_sma,
                indicators=indicators,
                risk_blocks=tuple(symbol_blocks),
            )
            ranking_rows.append(row)

            if symbol in current_positions:
                exit_reason = self._exit_reason(symbol, close, mean_5, positions[symbol], regime_ok, kill_switch_enabled)
                if exit_reason is not None:
                    exits.append(StrategyExit(symbol=symbol, reason=exit_reason))
                continue

            if z_score is not None and z_score >= self.z_score_entry and not symbol_blocks:
                entry_candidates.append(row)

        ranked = tuple(
            RankingSnapshot(
                symbol=item.symbol,
                rank=index + 1,
                return_60d=item.return_60d,
                above_sma_200=item.above_sma_200,
                indicators=item.indicators,
                risk_blocks=item.risk_blocks,
            )
            for index, item in enumerate(sorted(ranking_rows, key=lambda item: item.return_60d, reverse=True))
        )

        selected_symbols: set[str] = set()
        if regime_ok and not risk_blocks:
            max_signals = self.config.risk.max_clustered_signals or self.config.ranking.select_top_n
            selected_symbols = {
                item.symbol
                for item in sorted(entry_candidates, key=lambda item: item.return_60d, reverse=True)[:max_signals]
            }

        selected = self._build_selections(ranked, selected_symbols)
        orders = self._build_order_intents(selected, exits, mode=run_mode, portfolio_value=portfolio_value)
        return StrategyRebalance(
            strategy_name=self.name,
            mode=run_mode,
            timestamp=as_of,
            regime={
                "benchmark": self.config.regime.benchmark,
                "risk_on": regime_ok,
                "close": benchmark_close,
                "sma_200": benchmark_sma,
                "realized_vol_20d": None,
                "max_realized_vol": None,
            },
            rankings=ranked,
            selected=tuple(selected),
            exits=tuple(exits),
            risk_blocks=tuple(dict.fromkeys(risk_blocks)),
            orders=tuple(orders),
            indicator_snapshot={item.symbol: item.indicators for item in ranked},
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _exit_reason(
        self,
        symbol: str,
        close: float | None,
        mean_5: float | None,
        position: Mapping[str, object],
        regime_ok: bool,
        kill_switch_enabled: bool,
    ) -> str | None:
        if kill_switch_enabled:
            return "kill_switch_active_risk_reduction"
        if not regime_ok:
            return "benchmark_regime_failed"
        if close is None or mean_5 is None:
            return "insufficient_symbol_history"
        entry_price = _float(position.get("entry_price"))
        holding_bars = int(_float(position.get("holding_bars"), default=0.0))
        if close >= mean_5:
            return "returned_to_5d_mean"
        if entry_price is not None and close <= entry_price * (1.0 - (self.config.risk.stop_loss_pct or 0.03)):
            return "stop_loss_3pct"
        if self.config.risk.max_holding_bars is not None and holding_bars >= self.config.risk.max_holding_bars:
            return "max_holding_period_5_bars"
        return None

    def _build_selections(self, ranked: Sequence[RankingSnapshot], selected_symbols: set[str]) -> list[StrategySelection]:
        if not selected_symbols:
            return []
        raw_weight = min(1.0 / len(selected_symbols), self.config.risk.max_position_pct)
        gross = raw_weight * len(selected_symbols)
        target_weight = raw_weight if gross <= self.config.risk.max_gross_exposure_pct else raw_weight * (self.config.risk.max_gross_exposure_pct / gross)
        return [
            StrategySelection(
                symbol=item.symbol,
                target_weight=target_weight,
                reason="tested_positive_oversold_z_score",
                indicators=item.indicators,
            )
            for item in ranked
            if item.symbol in selected_symbols
        ]

    def _build_order_intents(
        self,
        selected: Sequence[StrategySelection],
        exits: Sequence[StrategyExit],
        *,
        mode: str,
        portfolio_value: float | None,
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for item in selected:
            notional = None if portfolio_value is None else portfolio_value * item.target_weight
            intents.append(
                OrderIntent(
                    strategy_name=self.name,
                    symbol=item.symbol,
                    side="buy",
                    target_weight=item.target_weight,
                    quantity=None,
                    notional=notional,
                    reason=item.reason,
                    mode=mode,  # type: ignore[arg-type]
                )
            )
        for item in exits:
            intents.append(
                OrderIntent(
                    strategy_name=self.name,
                    symbol=item.symbol,
                    side="sell",
                    target_weight=0.0,
                    quantity=None,
                    notional=None,
                    reason=item.reason,
                    mode=mode,  # type: ignore[arg-type]
                )
            )
        return intents


def _float(value: object, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
