from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping, Sequence

from trading_system.strategies._common import StrategyRiskProfile
from trading_system.strategies.indicators import (
    atr,
    close_values,
    ema,
    realized_volatility,
    relative_volume,
    rolling_return,
    rsi,
    sma,
    spread_bps,
)
from trading_system.strategies.rebalance import RankingSnapshot, StrategyExit, StrategyRebalance, StrategySelection
from trading_system.strategies.strategy_config import StrategyConfig, default_equity_etf_trend_regime_config
from trading_system.strategy.base import Strategy, StrategySignal
from trading_system.trading.order_intents import OrderIntent


class EquityEtfTrendRegimeV1(Strategy):
    name = "equity_etf_trend_regime_v1"
    family = "etf_rotation"
    description = "Daily liquid-ETF rotation gated by SPY 200SMA regime, realized volatility, trend, liquidity, and spread controls."
    universe = default_equity_etf_trend_regime_config().universe
    required_data = (
        "daily_bars_by_symbol",
        "quotes_by_symbol",
        "current_positions",
        "market_is_open",
        "data_stale",
        "kill_switch_enabled",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": True}
    config_schema = default_equity_etf_trend_regime_config().to_dict()
    risk_profile = StrategyRiskProfile(
        max_position_notional_usd=10_000.0,
        max_order_notional_usd=10_000.0,
        max_trades_per_day=3,
        max_open_positions=3,
        max_daily_loss_usd=250.0,
        stop_loss_pct=None,
        max_holding_minutes=None,
        allow_short=False,
    )
    default_enabled = True

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or default_equity_etf_trend_regime_config()

    def generate_signal(self, symbol: str, features: dict[str, object]) -> StrategySignal:
        bars_by_symbol = features.get("daily_bars_by_symbol")
        if not isinstance(bars_by_symbol, Mapping):
            return StrategySignal(self.name, symbol, "hold", 0.0, "missing daily bars")
        rebalance = self.rebalance(
            bars_by_symbol=bars_by_symbol,
            quotes_by_symbol=features.get("quotes_by_symbol") if isinstance(features.get("quotes_by_symbol"), Mapping) else None,
            current_positions=tuple(features.get("current_positions", ())) if isinstance(features.get("current_positions", ()), Sequence) else (),
            mode=str(features.get("mode", self.config.mode)),
            kill_switch_enabled=bool(features.get("kill_switch_enabled", False)),
            data_stale=bool(features.get("data_stale", False)),
        )
        for selection in rebalance.selected:
            if selection.symbol == symbol:
                return StrategySignal(
                    self.name,
                    symbol,
                    "buy",
                    0.75,
                    selection.reason,
                    target_weight=selection.target_weight,
                    indicators=selection.indicators,
                    risk_passed=not selection.indicators.get("risk_blocked", False),
                    timestamp=rebalance.timestamp,
                    mode=rebalance.mode,
                )
        for exit_item in rebalance.exits:
            if exit_item.symbol == symbol:
                return StrategySignal(self.name, symbol, "exit", 0.90, exit_item.reason, timestamp=rebalance.timestamp, mode=rebalance.mode)
        return StrategySignal(self.name, symbol, "hold", 0.0, "not selected", timestamp=rebalance.timestamp, mode=rebalance.mode)

    def rebalance(
        self,
        *,
        bars_by_symbol: Mapping[str, Sequence[object]],
        quotes_by_symbol: Mapping[str, object] | None = None,
        current_positions: Sequence[str] = (),
        mode: str | None = None,
        timestamp: datetime | None = None,
        kill_switch_enabled: bool = False,
        data_stale: bool = False,
        partial_session: bool = False,
        portfolio_value: float | None = None,
    ) -> StrategyRebalance:
        as_of = timestamp or datetime.now(UTC)
        run_mode = mode or self.config.mode
        positions = set(current_positions)
        quotes = quotes_by_symbol or {}
        risk_blocks: list[str] = []
        warnings: list[str] = []

        if not self.config.enabled:
            risk_blocks.append("strategy_disabled")
        if run_mode == "live" and not self.config.execution.allow_live_orders:
            risk_blocks.append("live_orders_disabled")
        if data_stale:
            risk_blocks.append("stale_data")
        if partial_session:
            risk_blocks.append("partial_session")
        if kill_switch_enabled:
            risk_blocks.append("kill_switch_active")

        benchmark_bars = bars_by_symbol.get(self.config.regime.benchmark, ())
        benchmark_closes = close_values(benchmark_bars)
        benchmark_sma = sma(benchmark_closes, self.config.regime.sma_days)
        benchmark_vol = realized_volatility(benchmark_closes, self.config.regime.realized_vol_days)
        benchmark_close = benchmark_closes[-1] if benchmark_closes else None
        risk_on = (
            benchmark_close is not None
            and benchmark_sma is not None
            and benchmark_vol is not None
            and (not self.config.regime.require_benchmark_above_sma or benchmark_close > benchmark_sma)
            and benchmark_vol <= self.config.regime.max_realized_vol
        )
        if benchmark_close is None or benchmark_sma is None or benchmark_vol is None:
            risk_blocks.append("insufficient_benchmark_history")
        elif not risk_on:
            risk_blocks.append("regime_filter_failed")

        ranking_rows: list[RankingSnapshot] = []
        for symbol in self.config.universe:
            bars = bars_by_symbol.get(symbol, ())
            closes = close_values(bars)
            symbol_blocks: list[str] = []
            symbol_sma = sma(closes, self.config.trend.sma_days)
            fast_ema = ema(closes, self.config.trend.ema_fast_days)
            slow_ema = ema(closes, self.config.trend.ema_slow_days)
            return_60d = rolling_return(closes, self.config.ranking.lookback_days)
            realized_vol = realized_volatility(closes, self.config.regime.realized_vol_days)
            rsi_value = rsi(closes, self.config.momentum.rsi_days)
            atr_value = atr(bars, self.config.risk.atr_days)
            relative_volume_value = relative_volume(bars, self.config.liquidity.relative_volume_days)
            quote_spread_bps = spread_bps(quotes.get(symbol))
            close = closes[-1] if closes else None
            above_sma = close is not None and symbol_sma is not None and close > symbol_sma

            if return_60d is None or close is None:
                symbol_blocks.append("insufficient_symbol_history")
            if self.config.trend.require_symbol_above_sma and not above_sma:
                symbol_blocks.append("symbol_sma_filter_failed")
            if fast_ema is None or slow_ema is None or fast_ema <= slow_ema:
                symbol_blocks.append("ema_trend_filter_failed")
            if self.config.momentum.enabled:
                if rsi_value is None:
                    symbol_blocks.append("rsi_unavailable")
                if self.config.momentum.min_rsi is not None and rsi_value is not None and rsi_value < self.config.momentum.min_rsi:
                    symbol_blocks.append("rsi_below_minimum")
                if self.config.momentum.max_rsi is not None and rsi_value is not None and rsi_value > self.config.momentum.max_rsi:
                    symbol_blocks.append("rsi_above_maximum")
            if self.config.liquidity.require_relative_volume:
                if relative_volume_value is None:
                    symbol_blocks.append("relative_volume_unavailable")
                elif self.config.liquidity.min_relative_volume is not None and relative_volume_value < self.config.liquidity.min_relative_volume:
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
                "sma_200": symbol_sma,
                "ema_20": fast_ema,
                "ema_50": slow_ema,
                "rsi_14": rsi_value,
                "atr_14": atr_value,
                "realized_vol_20d": realized_vol,
                "relative_volume_20d": relative_volume_value,
                "spread_bps": quote_spread_bps,
            }
            if return_60d is not None:
                ranking_rows.append(
                    RankingSnapshot(
                        symbol=symbol,
                        rank=0,
                        return_60d=return_60d,
                        above_sma_200=above_sma,
                        indicators=indicators,
                        risk_blocks=tuple(symbol_blocks),
                    )
                )

        ranked = sorted(ranking_rows, key=lambda item: item.return_60d, reverse=True)
        ranked = tuple(
            RankingSnapshot(
                symbol=item.symbol,
                rank=index + 1,
                return_60d=item.return_60d,
                above_sma_200=item.above_sma_200,
                indicators=item.indicators,
                risk_blocks=item.risk_blocks,
            )
            for index, item in enumerate(ranked)
        )

        tradeable = [item for item in ranked if not item.risk_blocks]
        selected_symbols: set[str] = set()
        if risk_on and not risk_blocks:
            selected_symbols = {item.symbol for item in tradeable[: self.config.ranking.select_top_n]}

        selected = self._build_selections(ranked, selected_symbols)
        exits = self._build_exits(positions, selected_symbols, risk_blocks)
        orders = self._build_order_intents(selected, exits, mode=run_mode, portfolio_value=portfolio_value)
        regime = {
            "benchmark": self.config.regime.benchmark,
            "risk_on": risk_on,
            "close": benchmark_close,
            "sma_200": benchmark_sma,
            "realized_vol_20d": benchmark_vol,
            "max_realized_vol": self.config.regime.max_realized_vol,
        }
        indicator_snapshot = {item.symbol: item.indicators for item in ranked}
        return StrategyRebalance(
            strategy_name=self.name,
            mode=run_mode,
            timestamp=as_of,
            regime=regime,
            rankings=ranked,
            selected=tuple(selected),
            exits=tuple(exits),
            risk_blocks=tuple(dict.fromkeys(risk_blocks)),
            orders=tuple(orders),
            indicator_snapshot=indicator_snapshot,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _build_selections(
        self,
        ranked: Sequence[RankingSnapshot],
        selected_symbols: set[str],
    ) -> list[StrategySelection]:
        if not selected_symbols:
            return []
        raw_weight = min(1.0 / len(selected_symbols), self.config.risk.max_position_pct)
        gross = raw_weight * len(selected_symbols)
        target_weight = raw_weight if gross <= self.config.risk.max_gross_exposure_pct else raw_weight * (self.config.risk.max_gross_exposure_pct / gross)
        selections: list[StrategySelection] = []
        for item in ranked:
            if item.symbol not in selected_symbols:
                continue
            selections.append(
                StrategySelection(
                    symbol=item.symbol,
                    target_weight=target_weight,
                    reason=f"top_{self.config.ranking.select_top_n}_rank_and_regime_passed",
                    indicators=item.indicators,
                )
            )
        return selections

    def _build_exits(self, positions: set[str], selected_symbols: set[str], risk_blocks: list[str]) -> list[StrategyExit]:
        exits: list[StrategyExit] = []
        for symbol in sorted(positions):
            if symbol in selected_symbols:
                continue
            if "kill_switch_active" in risk_blocks:
                reason = "kill_switch_active_risk_reduction"
            elif "regime_filter_failed" in risk_blocks or "insufficient_benchmark_history" in risk_blocks:
                reason = "regime_failed_cash_switch"
            else:
                reason = "deselected"
            exits.append(StrategyExit(symbol=symbol, reason=reason))
        return exits

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
