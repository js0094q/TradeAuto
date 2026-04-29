from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from trading_system.strategies.equity_etf_trend_regime import EquityEtfTrendRegimeV1
from trading_system.strategies.indicators import close_values, sma
from trading_system.strategies.rebalance import StrategyExit, StrategyRebalance
from trading_system.strategies.strategy_config import StrategyConfig, default_cross_market_high_beta_confirmation_config


class CrossMarketHighBetaConfirmationV1(EquityEtfTrendRegimeV1):
    name = "cross_market_high_beta_confirmation_v1"
    family = "overlay"
    description = "Paper-shadow high-beta ETF rotation gated by SPY regime plus BTC and ETH 50-day trend confirmation."
    universe = default_cross_market_high_beta_confirmation_config().universe
    required_data = (
        "daily_bars_by_symbol",
        "crypto_bars_by_symbol",
        "quotes_by_symbol",
        "current_positions",
        "data_stale",
        "kill_switch_enabled",
    )
    mode_support = {"shadow": True, "paper": True, "restricted_live": False}
    config_schema = default_cross_market_high_beta_confirmation_config().to_dict()
    default_enabled = False

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or default_cross_market_high_beta_confirmation_config()

    def rebalance(
        self,
        *,
        bars_by_symbol: Mapping[str, Sequence[object]],
        crypto_bars_by_symbol: Mapping[str, Sequence[object]] | None = None,
        quotes_by_symbol: Mapping[str, object] | None = None,
        current_positions: Sequence[str] = (),
        mode: str | None = None,
        timestamp: datetime | None = None,
        kill_switch_enabled: bool = False,
        data_stale: bool = False,
        partial_session: bool = False,
        portfolio_value: float | None = None,
    ) -> StrategyRebalance:
        base = super().rebalance(
            bars_by_symbol=bars_by_symbol,
            quotes_by_symbol=quotes_by_symbol,
            current_positions=current_positions,
            mode=mode,
            timestamp=timestamp,
            kill_switch_enabled=kill_switch_enabled,
            data_stale=data_stale,
            partial_session=partial_session,
            portfolio_value=portfolio_value,
        )
        crypto_maps = crypto_bars_by_symbol or {}
        btc_ok, btc_close, btc_sma = self._crypto_confirmed(crypto_maps.get("BTC/USD") or crypto_maps.get("BTCUSDT"))
        eth_ok, eth_close, eth_sma = self._crypto_confirmed(crypto_maps.get("ETH/USD") or crypto_maps.get("ETHUSDT"))
        crypto_blocks: list[str] = []
        if btc_close is None or btc_sma is None:
            crypto_blocks.append("btc_data_unavailable")
        elif not btc_ok:
            crypto_blocks.append("btc_confirmation_failed")
        if eth_close is None or eth_sma is None:
            crypto_blocks.append("eth_data_unavailable")
        elif not eth_ok:
            crypto_blocks.append("eth_confirmation_failed")

        regime = {
            **base.regime,
            "btc_close": btc_close,
            "btc_sma_50": btc_sma,
            "btc_confirmed": btc_ok,
            "eth_close": eth_close,
            "eth_sma_50": eth_sma,
            "eth_confirmed": eth_ok,
            "risk_on": bool(base.regime.get("risk_on")) and btc_ok and eth_ok,
        }
        if not crypto_blocks:
            return StrategyRebalance(
                strategy_name=self.name,
                mode=base.mode,
                timestamp=base.timestamp,
                regime=regime,
                rankings=base.rankings,
                selected=base.selected,
                exits=base.exits,
                risk_blocks=base.risk_blocks,
                orders=base.orders,
                indicator_snapshot=base.indicator_snapshot,
                warnings=base.warnings,
            )

        combined_blocks = tuple(dict.fromkeys((*base.risk_blocks, *crypto_blocks)))
        exits = tuple(StrategyExit(symbol=symbol, reason="crypto_confirmation_failed") for symbol in sorted(set(current_positions)))
        orders = tuple(self._build_order_intents((), exits, mode=base.mode, portfolio_value=portfolio_value))
        return StrategyRebalance(
            strategy_name=self.name,
            mode=base.mode,
            timestamp=base.timestamp,
            regime=regime,
            rankings=base.rankings,
            selected=(),
            exits=exits,
            risk_blocks=combined_blocks,
            orders=orders,
            indicator_snapshot=base.indicator_snapshot,
            warnings=base.warnings,
        )

    @staticmethod
    def _crypto_confirmed(bars: Sequence[object] | None) -> tuple[bool, float | None, float | None]:
        if not bars:
            return False, None, None
        closes = close_values(bars)
        trend = sma(closes, 50)
        close = closes[-1] if closes else None
        return (close is not None and trend is not None and close > trend), close, trend
