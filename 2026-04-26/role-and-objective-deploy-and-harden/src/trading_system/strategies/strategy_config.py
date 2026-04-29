from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RankingConfig:
    method: str = "return"
    lookback_days: int = 60
    select_top_n: int = 3


@dataclass(frozen=True)
class RegimeConfig:
    benchmark: str = "SPY"
    sma_days: int = 200
    require_benchmark_above_sma: bool = True
    realized_vol_days: int = 20
    max_realized_vol: float = 0.025


@dataclass(frozen=True)
class TrendConfig:
    require_symbol_above_sma: bool = True
    sma_days: int = 200
    ema_fast_days: int = 20
    ema_slow_days: int = 50


@dataclass(frozen=True)
class MomentumConfig:
    rsi_days: int = 14
    enabled: bool = False
    min_rsi: float | None = None
    max_rsi: float | None = None


@dataclass(frozen=True)
class StrategyRiskConfig:
    atr_days: int = 14
    max_position_pct: float = 0.25
    max_gross_exposure_pct: float = 1.0
    max_daily_loss_pct: float | None = None
    max_drawdown_pct: float | None = None
    cash_switch_on_regime_fail: bool = True
    stop_loss_pct: float | None = None
    max_holding_bars: int | None = None
    max_clustered_signals: int | None = None


@dataclass(frozen=True)
class LiquidityConfig:
    require_relative_volume: bool = False
    relative_volume_days: int = 20
    min_relative_volume: float | None = None
    require_spread_filter: bool = True
    max_spread_bps: float | None = None


@dataclass(frozen=True)
class ExecutionConfig:
    allow_live_orders: bool = False
    require_explicit_live_env: bool = True
    rebalance_after_market_close: bool = True
    order_type: str = "market"
    time_in_force: str = "day"


@dataclass(frozen=True)
class LoggingConfig:
    log_indicator_snapshot: bool = True
    log_rankings: bool = True
    log_rebalance_decisions: bool = True
    log_risk_blocks: bool = True


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    enabled: bool
    mode: str
    timeframe: str
    rebalance_frequency: str
    universe: tuple[str, ...]
    ranking: RankingConfig = field(default_factory=RankingConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    risk: StrategyRiskConfig = field(default_factory=StrategyRiskConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["universe"] = list(self.universe)
        return payload


def _mapping_for(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    return value if isinstance(value, Mapping) else {}


def strategy_config_from_mapping(payload: Mapping[str, Any]) -> StrategyConfig:
    return StrategyConfig(
        name=str(payload["name"]),
        enabled=bool(payload.get("enabled", False)),
        mode=str(payload.get("mode", "paper_shadow")),
        timeframe=str(payload.get("timeframe", "1Day")),
        rebalance_frequency=str(payload.get("rebalance_frequency", "daily")),
        universe=tuple(str(item) for item in payload.get("universe", ())),
        ranking=RankingConfig(**dict(_mapping_for(payload, "ranking"))),
        regime=RegimeConfig(**dict(_mapping_for(payload, "regime"))),
        trend=TrendConfig(**dict(_mapping_for(payload, "trend"))),
        momentum=MomentumConfig(**dict(_mapping_for(payload, "momentum"))),
        risk=StrategyRiskConfig(**dict(_mapping_for(payload, "risk"))),
        liquidity=LiquidityConfig(**dict(_mapping_for(payload, "liquidity"))),
        execution=ExecutionConfig(**dict(_mapping_for(payload, "execution"))),
        logging=LoggingConfig(**dict(_mapping_for(payload, "logging"))),
    )


def default_equity_etf_trend_regime_config() -> StrategyConfig:
    return StrategyConfig(
        name="equity_etf_trend_regime_v1",
        enabled=True,
        mode="paper",
        timeframe="1Day",
        rebalance_frequency="daily",
        universe=("SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "TLT", "GLD"),
        liquidity=LiquidityConfig(require_spread_filter=True, max_spread_bps=25.0),
        execution=ExecutionConfig(allow_live_orders=False, order_type="market"),
    )


def default_cross_market_high_beta_confirmation_config() -> StrategyConfig:
    return StrategyConfig(
        name="cross_market_high_beta_confirmation_v1",
        enabled=False,
        mode="paper_shadow",
        timeframe="1Day",
        rebalance_frequency="daily",
        universe=("QQQ", "IWM", "XLK", "XLY", "XLC"),
        ranking=RankingConfig(select_top_n=2),
        liquidity=LiquidityConfig(require_spread_filter=True, max_spread_bps=35.0),
        execution=ExecutionConfig(allow_live_orders=False, order_type="market"),
    )


def default_liquid_etf_mean_reversion_config() -> StrategyConfig:
    return StrategyConfig(
        name="liquid_etf_mean_reversion_v1",
        enabled=False,
        mode="paper_shadow",
        timeframe="1Day",
        rebalance_frequency="daily",
        universe=("SPY", "QQQ", "IWM", "TLT", "GLD"),
        ranking=RankingConfig(method="z_score", lookback_days=20, select_top_n=2),
        risk=StrategyRiskConfig(
            max_position_pct=0.20,
            max_gross_exposure_pct=0.50,
            stop_loss_pct=0.03,
            max_holding_bars=5,
            max_clustered_signals=2,
        ),
        liquidity=LiquidityConfig(require_spread_filter=True, max_spread_bps=25.0),
        execution=ExecutionConfig(allow_live_orders=False, order_type="market"),
    )


def load_default_strategy_configs() -> dict[str, StrategyConfig]:
    configs = (
        default_equity_etf_trend_regime_config(),
        default_cross_market_high_beta_confirmation_config(),
        default_liquid_etf_mean_reversion_config(),
    )
    return {config.name: config for config in configs}


def validate_strategy_config(config: StrategyConfig) -> tuple[str, ...]:
    errors: list[str] = []
    if config.mode == "live" and not config.execution.allow_live_orders:
        errors.append("live mode requires execution.allow_live_orders=true")
    if config.execution.allow_live_orders and config.mode != "live":
        errors.append("allow_live_orders requires mode=live")
    if config.execution.allow_live_orders and config.name != "equity_etf_trend_regime_v1":
        errors.append("only explicitly promoted default strategy may enable live orders")
    if config.ranking.lookback_days <= 0:
        errors.append("ranking.lookback_days must be positive")
    if config.ranking.select_top_n <= 0:
        errors.append("ranking.select_top_n must be positive")
    if not config.universe:
        errors.append("universe must not be empty")
    if config.risk.max_position_pct <= 0.0:
        errors.append("risk.max_position_pct must be positive")
    if config.risk.max_gross_exposure_pct <= 0.0:
        errors.append("risk.max_gross_exposure_pct must be positive")
    if config.liquidity.max_spread_bps is not None and config.liquidity.max_spread_bps <= 0.0:
        errors.append("liquidity.max_spread_bps must be positive when set")
    return tuple(errors)
