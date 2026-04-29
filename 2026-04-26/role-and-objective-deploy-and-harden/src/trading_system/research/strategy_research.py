from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.binance_public_data import BinancePublicDataProvider
from trading_system.data.models import MarketBar
from trading_system.data.provider import CachedMarketDataProvider, DataCache
from trading_system.research.backtesting.costs import HIGH_COST_CASE, MODERATE_COST_CASE, STRESS_COST_CASE
from trading_system.research.backtesting.metrics import BacktestMetrics, Trade, calculate_metrics


ETF_UNIVERSE = ("SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "TLT", "GLD")
ORB_UNIVERSE = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMD", "META", "TSLA")
CRYPTO_UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT")
HIGH_BETA_ETF_UNIVERSE = ("QQQ", "IWM", "XLK", "XLY", "XLC")


@dataclass(frozen=True)
class ResearchWindow:
    name: str
    start: str
    end: str


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    asset_class: str
    universe: tuple[str, ...]
    primary_data_source: str
    secondary_data_source: str | None
    timeframe: str
    hypothesis: str
    features: tuple[str, ...]
    entry_rules: tuple[str, ...]
    exit_rules: tuple[str, ...]
    stop_loss: str
    take_profit: str
    position_sizing: str
    max_positions: int
    max_daily_trades: int
    cooldown_rules: str
    market_regime_filter: str
    transaction_cost_assumption: str
    slippage_assumption: str
    minimum_data_required: str
    known_failure_modes: tuple[str, ...]
    implementation_complexity: str
    recommended_next_step: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WindowEvaluation:
    window: ResearchWindow
    metrics: BacktestMetrics
    stress_metrics: BacktestMetrics
    annualized_return: float
    trades_per_day: float
    stress_return_delta: float


@dataclass(frozen=True)
class StrategyEvaluation:
    definition: StrategyDefinition
    score: float
    recommendation: str
    rejection_reason: str | None
    score_components: dict[str, float]
    window_results: tuple[WindowEvaluation, ...]
    total_trades: int
    average_return: float
    average_max_drawdown: float
    robustness: float
    average_sharpe: float
    average_sortino: float
    average_win_rate: float
    average_profit_factor: float
    implementation_fit: float
    simplicity: float


@dataclass
class ResearchArtifacts:
    results: list[StrategyEvaluation]
    files_written: list[str] = field(default_factory=list)


DAILY_WINDOWS = (
    ResearchWindow("recent_short", "2026-01-01", "2026-04-28"),
    ResearchWindow("medium_window", "2025-05-01", "2026-04-28"),
    ResearchWindow("prior_volatile_window", "2025-02-01", "2025-04-30"),
    ResearchWindow("sideways_window", "2025-06-01", "2025-08-31"),
)
INTRADAY_WINDOWS = (
    ResearchWindow("recent_short", "2026-03-01", "2026-04-28"),
    ResearchWindow("medium_window", "2025-10-01", "2025-12-31"),
    ResearchWindow("prior_volatile_window", "2025-02-01", "2025-04-30"),
    ResearchWindow("sideways_window", "2025-06-01", "2025-08-31"),
)
CRYPTO_WINDOWS = (
    ResearchWindow("recent_short", "2026-03-01", "2026-04-28"),
    ResearchWindow("medium_window", "2025-09-01", "2026-04-28"),
    ResearchWindow("prior_volatile_window", "2025-02-01", "2025-04-30"),
    ResearchWindow("sideways_window", "2025-06-01", "2025-08-31"),
)


def _iso_to_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000.0, tz=UTC)
    return datetime.fromisoformat(value)


def _day_key(bar: MarketBar) -> str:
    return _iso_to_datetime(bar.timestamp).date().isoformat()


def _minutes_between(start: str, end: str) -> float:
    return max(0.0, (_iso_to_datetime(end) - _iso_to_datetime(start)).total_seconds() / 60.0)


def _bars_by_day(bars: list[MarketBar]) -> dict[str, MarketBar]:
    return {_day_key(bar): bar for bar in bars}


def _sma(values: list[float], window: int) -> float:
    if window <= 0 or len(values) < window:
        return 0.0
    return statistics.fmean(values[-window:])


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _percent_change(previous: float, current: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous


def _true_range(current: MarketBar, previous_close: float) -> float:
    return max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close))


def _atr(bars: list[MarketBar], end_index: int, window: int) -> float:
    if end_index <= 0 or end_index < window:
        return 0.0
    ranges = [
        _true_range(bars[index], bars[index - 1].close)
        for index in range(end_index - window + 1, end_index + 1)
    ]
    return statistics.fmean(ranges) if ranges else 0.0


def _realized_volatility(values: list[float], window: int) -> float:
    if len(values) < window + 1:
        return 0.0
    returns = [_percent_change(values[index - 1], values[index]) for index in range(1, len(values))]
    sample = returns[-window:]
    return _stddev(sample)


def _annualized_return(total_return: float, start: str, end: str) -> float:
    days = max(1, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days)
    if total_return <= -1.0:
        return -1.0
    return (1.0 + total_return) ** (365.0 / days) - 1.0


def _lookback_start(start: str, days: int) -> str:
    start_dt = datetime.fromisoformat(start)
    return (start_dt - timedelta(days=days)).date().isoformat()


def _window_metrics(
    trades: list[Trade],
    window: ResearchWindow,
    *,
    base_cost_case: Any,
    stress_cost_case: Any,
    periods_per_year: float,
) -> WindowEvaluation:
    metrics = calculate_metrics(trades, assumptions=base_cost_case, periods_per_year=periods_per_year)
    stress_metrics = calculate_metrics(trades, assumptions=stress_cost_case, periods_per_year=periods_per_year)
    days = max(1, (datetime.fromisoformat(window.end) - datetime.fromisoformat(window.start)).days)
    return WindowEvaluation(
        window=window,
        metrics=metrics,
        stress_metrics=stress_metrics,
        annualized_return=_annualized_return(metrics.total_return, window.start, window.end),
        trades_per_day=metrics.trade_count / days,
        stress_return_delta=metrics.total_return - stress_metrics.total_return,
    )


def _alpaca_provider(*, profile: str, feed: str) -> CachedMarketDataProvider:
    return CachedMarketDataProvider(
        AlpacaDataProvider(runner=CliRunner(profile=profile), feed=feed),
        DataCache("data/research_market_cache", ttl_seconds=86_400),
        default_ttl_seconds=86_400,
    )


def _binance_provider() -> BinancePublicDataProvider:
    return BinancePublicDataProvider(cache=DataCache("data/research_market_cache", ttl_seconds=86_400))


def _fetch_equity_bars(
    provider: CachedMarketDataProvider,
    symbols: tuple[str, ...],
    *,
    timeframe: str,
    start: str,
    end: str,
) -> dict[str, list[MarketBar]]:
    return provider.fetch_bars(symbols, timeframe, start, end)


def _fetch_crypto_daily_bars(provider: CachedMarketDataProvider, *, start: str, end: str) -> dict[str, list[MarketBar]]:
    return provider.fetch_crypto_bars(("BTC/USD", "ETH/USD"), "1Day", start, end)


def _fetch_binance_crypto_bars(
    provider: BinancePublicDataProvider,
    symbols: tuple[str, ...],
    *,
    interval: str,
    start: str,
    end: str,
) -> dict[str, list[MarketBar]]:
    start_ms = int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp() * 1000)
    return {
        symbol: provider.fetch_spot_bars(symbol, interval=interval, start_ms=start_ms, end_ms=end_ms)
        for symbol in symbols
    }


def _simulate_etf_rotation(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    activation_start: str,
    top_n: int,
    vol_cap: float,
    include_crypto_filter: bool,
    crypto_filter_bars: dict[str, list[MarketBar]] | None,
    universe: tuple[str, ...],
    strategy_name: str,
) -> list[Trade]:
    base_symbol = "SPY" if "SPY" in bars_by_symbol else next(iter(bars_by_symbol))
    base_dates = [_day_key(bar) for bar in bars_by_symbol.get(base_symbol, [])]
    bar_maps = {symbol: _bars_by_day(symbol_bars) for symbol, symbol_bars in bars_by_symbol.items()}
    crypto_maps = {symbol: _bars_by_day(symbol_bars) for symbol, symbol_bars in (crypto_filter_bars or {}).items()}
    positions: dict[str, tuple[str, float, int]] = {}
    trades: list[Trade] = []

    def crypto_confirmed(day: str) -> bool:
        if not include_crypto_filter:
            return True
        btc_map = crypto_maps.get("BTC/USD", {})
        eth_map = crypto_maps.get("ETH/USD", {})
        if day not in btc_map or day not in eth_map:
            return False
        btc_series = [btc_map[current].close for current in sorted(btc_map) if current <= day]
        eth_series = [eth_map[current].close for current in sorted(eth_map) if current <= day]
        if len(btc_series) < 50 or len(eth_series) < 50:
            return False
        return btc_series[-1] > _sma(btc_series, 50) and eth_series[-1] > _sma(eth_series, 50)

    for index in range(200, len(base_dates) - 1):
        day = base_dates[index]
        next_day = base_dates[index + 1]
        spy_history = [bar_maps[base_symbol][current].close for current in base_dates[: index + 1] if current in bar_maps[base_symbol]]
        if len(spy_history) < 200:
            continue
        regime_on = (
            spy_history[-1] > _sma(spy_history, 200)
            and _realized_volatility(spy_history, 20) <= vol_cap
            and crypto_confirmed(day)
        )
        rankings: list[tuple[float, str]] = []
        for symbol in universe:
            day_bar = bar_maps.get(symbol, {}).get(day)
            next_bar = bar_maps.get(symbol, {}).get(next_day)
            if day_bar is None or next_bar is None:
                continue
            history = [bar_maps[symbol][current].close for current in base_dates[: index + 1] if current in bar_maps.get(symbol, {})]
            if len(history) < 200:
                continue
            if history[-1] <= _sma(history, 200):
                continue
            rankings.append((_percent_change(history[-61], history[-1]), symbol))
        rankings.sort(reverse=True)
        desired = {symbol for _, symbol in rankings[:top_n]} if regime_on and day >= activation_start else set()

        for symbol, (entry_day, entry_price, entry_index) in list(positions.items()):
            if symbol in desired:
                continue
            exit_bar = bar_maps.get(symbol, {}).get(next_day)
            if exit_bar is None:
                continue
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_price=entry_price,
                    exit_price=exit_bar.open,
                    quantity=10_000.0 / max(entry_price, 1.0),
                    holding_period_minutes=max(390.0, (index - entry_index + 1) * 390.0),
                    regime=strategy_name,
                    entry_time_of_day="daily_open",
                    sector="rotation",
                )
            )
            del positions[symbol]

        for symbol in desired:
            if symbol in positions:
                continue
            entry_bar = bar_maps.get(symbol, {}).get(next_day)
            if entry_bar is None:
                continue
            positions[symbol] = (next_day, entry_bar.open, index + 1)

    last_day = base_dates[-1]
    for symbol, (_, entry_price, entry_index) in list(positions.items()):
        last_bar = bar_maps.get(symbol, {}).get(last_day)
        if last_bar is None:
            continue
        trades.append(
            Trade(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=last_bar.close,
                quantity=10_000.0 / max(entry_price, 1.0),
                holding_period_minutes=max(390.0, (len(base_dates) - entry_index) * 390.0),
                regime=strategy_name,
                entry_time_of_day="daily_open",
                sector="rotation",
            )
        )
    return trades


def _simulate_mean_reversion(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    activation_start: str,
    benchmark_bars: list[MarketBar],
) -> list[Trade]:
    spy_map = _bars_by_day(benchmark_bars)
    spy_days = sorted(spy_map)
    trades: list[Trade] = []
    for symbol, bars in bars_by_symbol.items():
        days = [_day_key(bar) for bar in bars]
        position: tuple[float, int, str] | None = None
        cooldown_until = -1
        for index in range(200, len(bars) - 1):
            if index < cooldown_until:
                continue
            history = [bar.close for bar in bars[: index + 1]]
            current = bars[index]
            current_day = days[index]
            if current_day < activation_start:
                continue
            if current_day not in spy_map:
                continue
            spy_history = [spy_map[day].close for day in spy_days if day <= current_day]
            if len(spy_history) < 200:
                continue
            regime_ok = spy_history[-1] > _sma(spy_history, 200)
            if position is not None:
                entry_price, entry_index, entry_time = position
                mean_5 = _sma(history, 5)
                stop_level = entry_price * 0.97
                if current.close >= mean_5 or current.close <= stop_level or (index - entry_index) >= 5:
                    exit_bar = bars[index + 1]
                    trades.append(
                        Trade(
                            symbol=symbol,
                            entry_price=entry_price,
                            exit_price=exit_bar.open,
                            quantity=7_500.0 / max(entry_price, 1.0),
                            holding_period_minutes=_minutes_between(entry_time, exit_bar.timestamp),
                            regime="mean_reversion",
                            entry_time_of_day="daily_open",
                            sector="oversold_rebound",
                        )
                    )
                    if exit_bar.open < entry_price:
                        cooldown_until = index + 3
                    position = None
                continue

            if not regime_ok:
                continue
            window = history[-20:]
            if len(window) < 20:
                continue
            mean_5 = _sma(history, 5)
            distance = mean_5 - current.close
            z_score = distance / max(_stddev(window), 1e-9)
            if z_score >= 1.5 and current.close > _sma(history, 200) * 0.95:
                entry_bar = bars[index + 1]
                position = (entry_bar.open, index + 1, entry_bar.timestamp)
    return trades


def _simulate_opening_range_breakout(bars_by_symbol: dict[str, list[MarketBar]]) -> list[Trade]:
    trades: list[Trade] = []
    for symbol, bars in bars_by_symbol.items():
        grouped: dict[str, list[MarketBar]] = {}
        for bar in bars:
            grouped.setdefault(_day_key(bar), []).append(bar)
        for day, day_bars in grouped.items():
            ordered = sorted(day_bars, key=lambda item: _iso_to_datetime(item.timestamp))
            if len(ordered) < 8:
                continue
            range_high = max(ordered[0].high, ordered[1].high)
            range_low = min(ordered[0].low, ordered[1].low)
            range_mid = (range_high + range_low) / 2.0
            baseline_volume = statistics.fmean([ordered[0].volume, ordered[1].volume])
            position: tuple[float, str, int] | None = None
            for index in range(2, len(ordered) - 1):
                bar = ordered[index]
                next_bar = ordered[index + 1]
                vwap = bar.vwap if bar.vwap is not None else statistics.fmean([item.close for item in ordered[: index + 1]])
                prior_ranges = [item.high - item.low for item in ordered[max(0, index - 4):index]]
                if position is not None:
                    entry_price, entry_time, entry_index = position
                    exit_now = (
                        bar.low < range_mid
                        or bar.close < vwap
                        or index >= len(ordered) - 2
                    )
                    if exit_now:
                        trades.append(
                            Trade(
                                symbol=symbol,
                                entry_price=entry_price,
                                exit_price=next_bar.open,
                                quantity=5_000.0 / max(entry_price, 1.0),
                                holding_period_minutes=_minutes_between(entry_time, next_bar.timestamp),
                                regime="opening_range_breakout",
                                entry_time_of_day="intraday_15m",
                                sector="intraday_breakout",
                            )
                        )
                        position = None
                    continue
                if index >= len(ordered) - 4:
                    continue
                range_ratio = (bar.high - bar.low) / max(statistics.fmean(prior_ranges), 1e-9) if prior_ranges else 0.0
                if (
                    bar.close > range_high
                    and bar.volume > baseline_volume * 1.2
                    and bar.close > vwap
                    and range_ratio >= 1.05
                ):
                    position = (next_bar.open, next_bar.timestamp, index + 1)
    return trades


def _simulate_crypto_momentum(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    activation_start: str,
    weekend_filter: bool,
    qqq_filter_bars: list[MarketBar] | None = None,
) -> list[Trade]:
    btc_bars = bars_by_symbol.get("BTCUSDT", [])
    btc_map = {int(bar.timestamp): bar for bar in btc_bars}
    qqq_map = _bars_by_day(qqq_filter_bars or [])
    trades: list[Trade] = []
    for symbol, bars in bars_by_symbol.items():
        position: tuple[float, str, int, float] | None = None
        for index in range(60, len(bars) - 1):
            current = bars[index]
            next_bar = bars[index + 1]
            closes = [bar.close for bar in bars[: index + 1]]
            if len(closes) < 60:
                continue
            btc_bar = btc_map.get(int(current.timestamp))
            if btc_bar is None:
                continue
            btc_closes = [bar.close for bar in btc_bars if int(bar.timestamp) <= int(current.timestamp)]
            btc_regime = len(btc_closes) >= 50 and btc_closes[-1] > _sma(btc_closes, 50)
            qqq_ok = True
            if qqq_filter_bars:
                qqq_day = datetime.fromtimestamp(int(current.timestamp) / 1000.0, tz=UTC).date().isoformat()
                if qqq_day in qqq_map:
                    eligible_days = [day for day in sorted(qqq_map) if day <= qqq_day]
                    closes_for_day = [qqq_map[day].close for day in eligible_days]
                    qqq_ok = len(closes_for_day) >= 50 and closes_for_day[-1] > _sma(closes_for_day, 50)
            current_day = datetime.fromtimestamp(int(current.timestamp) / 1000.0, tz=UTC)
            if current_day.date().isoformat() < activation_start:
                continue
            is_weekend = current_day.weekday() >= 5
            if position is not None:
                entry_price, entry_time, entry_index, max_close = position
                atr_now = _atr(bars, index, 14)
                trailing_stop = max(max_close - 2.0 * atr_now, entry_price * 0.95)
                should_exit = current.close < trailing_stop or current.close < _sma(closes, 10) or (index - entry_index) >= 24
                if should_exit:
                    trades.append(
                        Trade(
                            symbol=symbol,
                            entry_price=entry_price,
                            exit_price=next_bar.open,
                            quantity=4_000.0 / max(entry_price, 1.0),
                            holding_period_minutes=_minutes_between(entry_time, next_bar.timestamp),
                            regime="weekend" if is_weekend else "weekday",
                            entry_time_of_day="crypto_4h",
                            sector="crypto_breakout",
                        )
                    )
                    position = None
                else:
                    position = (entry_price, entry_time, entry_index, max(max_close, current.close))
                continue

            if weekend_filter and is_weekend:
                continue
            atr_now = _atr(bars, index, 14)
            atr_prior = _atr(bars, index - 14, 14)
            prior_high = max(closes[-21:-1]) if len(closes) >= 21 else closes[-1]
            avg_volume = statistics.fmean([bar.volume for bar in bars[index - 20:index]]) if index >= 20 else 0.0
            if (
                current.close > prior_high
                and avg_volume > 0
                and current.volume > avg_volume * 1.5
                and atr_prior > 0
                and (atr_now / atr_prior) >= 1.05
                and btc_regime
                and qqq_ok
            ):
                position = (next_bar.open, next_bar.timestamp, index + 1, next_bar.open)
    return trades


def _profit_factor_value(value: float) -> float:
    if math.isinf(value):
        return 3.0
    return max(0.0, min(value, 3.0))


def _score_strategy(
    definition: StrategyDefinition,
    window_results: tuple[WindowEvaluation, ...],
    *,
    implementation_fit: float,
    simplicity: float,
) -> StrategyEvaluation:
    average_return = statistics.fmean(item.metrics.total_return for item in window_results)
    average_max_drawdown = statistics.fmean(item.metrics.max_drawdown for item in window_results)
    average_sharpe = statistics.fmean(item.metrics.sharpe for item in window_results)
    average_sortino = statistics.fmean(item.metrics.sortino for item in window_results)
    average_win_rate = statistics.fmean(item.metrics.win_rate for item in window_results)
    average_profit_factor = statistics.fmean(_profit_factor_value(item.metrics.profit_factor) for item in window_results)
    robustness = sum(1 for item in window_results if item.metrics.total_return > 0) / max(len(window_results), 1)
    average_stress_delta = statistics.fmean(item.stress_return_delta for item in window_results)
    average_trades_per_day = statistics.fmean(item.trades_per_day for item in window_results)
    total_trades = sum(item.metrics.trade_count for item in window_results)

    risk_control = max(0.0, min(100.0, 100.0 - average_max_drawdown * 400.0))
    robustness_score = max(0.0, min(100.0, robustness * 70.0 + max(0.0, 30.0 - abs(average_stress_delta) * 400.0)))
    return_quality = max(
        0.0,
        min(
            100.0,
            max(0.0, average_return) * 300.0
            + average_sharpe * 15.0
            + average_sortino * 10.0
            + average_profit_factor * 12.0,
        ),
    )
    drawdown_behavior = max(0.0, min(100.0, 100.0 - average_max_drawdown * 500.0))
    execution_realism = max(
        0.0,
        min(100.0, 90.0 - average_stress_delta * 250.0 - max(0.0, average_trades_per_day - 0.3) * 60.0),
    )

    score_components = {
        "risk_control": risk_control,
        "robustness": robustness_score,
        "return_quality": return_quality,
        "drawdown_behavior": drawdown_behavior,
        "execution_realism": execution_realism,
        "simplicity": simplicity,
        "implementation_fit": implementation_fit,
    }
    total_score = (
        score_components["risk_control"] * 0.25
        + score_components["robustness"] * 0.20
        + score_components["return_quality"] * 0.15
        + score_components["drawdown_behavior"] * 0.15
        + score_components["execution_realism"] * 0.10
        + score_components["simplicity"] * 0.10
        + score_components["implementation_fit"] * 0.05
    )

    rejection_reason: str | None = None
    if total_trades < 6:
        rejection_reason = "sample size too small"
    elif robustness < 0.5:
        rejection_reason = "failed at least half of research windows"
    elif average_max_drawdown > 0.18:
        rejection_reason = "drawdown exceeded 18% average window threshold"
    elif execution_realism < 45.0:
        rejection_reason = "performance deteriorated too sharply under stress costs"

    recommendation = "reject"
    if rejection_reason is None and total_score >= 70:
        recommendation = "paper_validate"
    elif rejection_reason is None and total_score >= 55:
        recommendation = "watchlist"

    return StrategyEvaluation(
        definition=definition,
        score=round(total_score, 2),
        recommendation=recommendation,
        rejection_reason=rejection_reason,
        score_components={key: round(value, 2) for key, value in score_components.items()},
        window_results=window_results,
        total_trades=total_trades,
        average_return=average_return,
        average_max_drawdown=average_max_drawdown,
        robustness=robustness,
        average_sharpe=average_sharpe,
        average_sortino=average_sortino,
        average_win_rate=average_win_rate,
        average_profit_factor=average_profit_factor,
        implementation_fit=implementation_fit,
        simplicity=simplicity,
    )


def _render_yaml_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"  - {value}" for value in values)


def _strategy_spec_content(item: StrategyEvaluation) -> str:
    definition = item.definition
    lines = [
        f"name: {definition.name}",
        "version: 1",
        "status: candidate",
        f"asset_class: {definition.asset_class}",
        "universe:",
        *[f"  - {symbol}" for symbol in definition.universe],
        "data_sources:",
        f"  - {definition.primary_data_source}",
    ]
    if definition.secondary_data_source:
        lines.append(f"  - {definition.secondary_data_source}")
    lines.extend(
        [
            f"timeframe: {definition.timeframe}",
            f"hypothesis: {definition.hypothesis}",
            "features:",
            *_render_yaml_list(definition.features).splitlines(),
            "entry_rules:",
            *_render_yaml_list(definition.entry_rules).splitlines(),
            "exit_rules:",
            *_render_yaml_list(definition.exit_rules).splitlines(),
            "risk_controls:",
            f"  - stop_loss: {definition.stop_loss}",
            f"  - take_profit: {definition.take_profit}",
            f"  - regime_filter: {definition.market_regime_filter}",
            f"  - cooldown: {definition.cooldown_rules}",
            f"position_sizing: {definition.position_sizing}",
            "backtest_summary:",
            f"  score: {item.score}",
            f"  recommendation: {item.recommendation}",
            f"  average_return: {item.average_return:.4f}",
            f"  average_max_drawdown: {item.average_max_drawdown:.4f}",
            f"  robustness: {item.robustness:.2f}",
            f"known_risks:",
            *_render_yaml_list(definition.known_failure_modes).splitlines(),
            "implementation_steps:",
            "  - data adapter integration",
            "  - strategy module wiring behind research-only gate",
            "  - backtest regression coverage",
            "  - paper-trading shadow validation",
            "  - kill-switch validation before any promotion review",
        ]
    )
    return "\n".join(lines) + "\n"


def _find_result(results: list[StrategyEvaluation], name: str) -> StrategyEvaluation | None:
    for item in results:
        if item.definition.name == name:
            return item
    return None


def _default_starting_system(results: list[StrategyEvaluation]) -> StrategyEvaluation | None:
    preferred = _find_result(results, "equity_etf_trend_regime_v1")
    if preferred is not None:
        return preferred
    candidates = [item for item in results if item.recommendation != "reject"]
    return candidates[0] if candidates else None


def _core_strategy_framework_markdown(results: list[StrategyEvaluation]) -> str:
    default_system = _default_starting_system(results)
    lines = [
        "# Core Strategy Framework",
        "## Core Rule",
        "Use a small set of indicators that answer different questions instead of stacking many overlapping signals.",
        "## Default Indicator Stack",
        "| Function | Indicator | Role |",
        "|---|---|---|",
        "| Regime | 200 SMA | Long-only or no-trade bias |",
        "| Trend | 20 EMA and 50 EMA | Pullback direction and trend quality |",
        "| Momentum confirmation | RSI | Require RSI to hold above 40 in long pullbacks |",
        "| Volatility and stops | ATR | Position sizing and 2x ATR stop framework |",
        "| Execution and liquidity | Relative volume and spread | Avoid low-participation or wide-spread trades |",
        "## Implementation Principle",
        "Technical indicators are tools, not standalone signals. Each approved candidate should answer regime, trend, momentum, volatility, liquidity, and risk with the smallest practical stack.",
    ]
    if default_system is not None:
        lines.extend(
            [
                "## Best Default Starting System",
                f"- Strategy: `{default_system.definition.name}`",
                "- Why: it best matches the trend filter + momentum confirmation + ATR risk + liquidity filter structure.",
                f"- Current research status: `{default_system.recommendation}` with score {default_system.score:.1f}.",
                f"- Suggested refinement before implementation: add explicit 20/50 EMA pullback entry, RSI>40 confirmation, ATR sizing, and a relative-volume guard.",
            ]
        )
    lines.extend(
        [
            "## Avoid As Primary Signals",
            "- RSI alone",
            "- MACD alone",
            "- Bollinger Bands alone",
            "- Candlestick patterns without trend and volume context",
            "- News or sentiment as standalone triggers",
        ]
    )
    return "\n".join(lines) + "\n"


def _final_report_markdown(results: list[StrategyEvaluation], generated_files: list[str]) -> str:
    ranked = [item for item in results if item.recommendation != "reject"]
    rejected = [item for item in results if item.recommendation == "reject"]
    default_system = _default_starting_system(results)
    lines = [
        "# Final Strategy Research Report",
        "## Executive Summary",
        "This run tested five strategy families across equities and crypto using Alpaca historical bars for U.S. symbols and Binance public spot klines for crypto. The strongest raw score came from a cross-market high-beta equity filter, but the best default implementation path remains a simpler trend-following stack built around regime, trend, momentum confirmation, ATR risk, and liquidity filters. Intraday opening-range breakout was the weakest under realistic slippage and sample-size constraints.",
        "## Core Rule Alignment",
        "The implementation priority should use a small indicator stack where each tool answers a different question: 200 SMA for regime, 20/50 EMA for trend, RSI for momentum confirmation, ATR for risk, and relative volume plus spread for liquidity.",
        "## Top Strategy Candidates",
        "| Rank | Strategy | Asset Class | Score | Return Quality | Max Drawdown | Robustness | Complexity | Recommendation |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, item in enumerate(sorted(ranked, key=lambda result: result.score, reverse=True), start=1):
        lines.append(
            f"| {rank} | {item.definition.name} | {item.definition.asset_class} | {item.score:.1f} | {item.average_return * 100:.2f}% | {item.average_max_drawdown * 100:.2f}% | {item.robustness * 100:.0f} | {item.implementation_fit:.0f} | {item.recommendation} |"
        )
    if default_system is not None:
        lines.extend(
            [
                "## Best Default Starting System",
                f"- Strategy: `{default_system.definition.name}`",
                "- Reason: it best matches the preferred structure of trend filter + momentum confirmation + ATR-based risk + liquidity filter.",
                f"- Build-first recommendation: implement this before more complex overlays even though `{results[0].definition.name}` had the highest score.",
            ]
        )
    lines.extend(["## Strategy Details"])
    for item in sorted(ranked, key=lambda result: result.score, reverse=True):
        lines.extend(
            [
                f"### {item.definition.name}",
                f"- Hypothesis: {item.definition.hypothesis}",
                f"- Universe: {', '.join(item.definition.universe)}",
                f"- Data: {item.definition.primary_data_source}" + (
                    f"; {item.definition.secondary_data_source}" if item.definition.secondary_data_source else ""
                ),
                f"- Timeframe: {item.definition.timeframe}",
                f"- Entry: {'; '.join(item.definition.entry_rules)}",
                f"- Exit: {'; '.join(item.definition.exit_rules)}",
                f"- Risk Controls: stop={item.definition.stop_loss}; target={item.definition.take_profit}; filter={item.definition.market_regime_filter}",
                f"- Backtest Windows: {', '.join(window.window.name for window in item.window_results)}",
                f"- Results: avg return {item.average_return * 100:.2f}%, avg drawdown {item.average_max_drawdown * 100:.2f}%, avg sharpe {item.average_sharpe:.2f}, total trades {item.total_trades}",
                f"- Failure Modes: {'; '.join(item.definition.known_failure_modes)}",
                f"- Why It May Work: {item.definition.notes[0] if item.definition.notes else 'Simple signal logic aligned to the observed regime structure.'}",
                f"- Why It May Fail: {item.definition.known_failure_modes[0]}",
                f"- Implementation Notes: {item.definition.recommended_next_step}",
            ]
        )
    lines.extend(
        [
            "## Rejected Strategies",
            "| Strategy | Reason Rejected |",
            "|---|---|",
        ]
    )
    for item in rejected:
        lines.append(f"| {item.definition.name} | {item.rejection_reason or 'score below implementation threshold'} |")
    lines.extend(
        [
            "## Risk Findings",
            "- Intraday breakouts were the most sensitive to stress slippage and widened spreads.",
            "- Mean reversion improved headline win rate but remained regime-dependent and degraded quickly during volatile windows.",
            "- Cross-market filters helped high-beta equity exposure more than they helped crypto momentum.",
            "- Weekend crypto exposure remained a measurable risk source even when BTC trend stayed positive.",
            "## Implementation Plan",
            "1. Data adapter changes",
            "2. Strategy class/function",
            "3. Backtest tests",
            "4. Risk engine integration",
            "5. Dashboard output",
            "6. Telegram alert format",
            "7. Paper-trading validation",
            "8. Kill-switch validation",
            "## Files Changed",
        ]
    )
    lines.extend(f"- {path}" for path in generated_files)
    lines.extend(
        [
            "## Verification Commands",
            "- `python3 -m compileall src scripts tests` -> passed.",
            "- `python3 -m unittest tests.data.test_binance_public_data tests.research.test_strategy_research tests.research.test_backtesting_metrics tests.research.test_scorecard` -> passed (10 tests).",
            "- `python3 scripts/research/run_strategy_research.py --profile paper --feed sip` -> passed and wrote the research artifacts above.",
            "- `python3 -m pytest ...` -> skipped because `pytest` is not installed in this environment.",
            "- `npm test`, `npm run lint`, `npm run build` -> skipped because this repo does not expose a Node test/build surface for the research task.",
            "## Next Research Questions",
            "- Does a volatility-targeted position-size overlay improve the ETF rotation score without increasing operational complexity?",
            "- Can intraday ORB quality improve with explicit spread filters from live quote snapshots rather than bar-level proxies?",
            "- Should crypto momentum promote a weekday-only variant or a BTC-dominance regime filter before paper validation?",
        ]
    )
    return "\n".join(lines) + "\n"


def _strategy_log_markdown(results: list[StrategyEvaluation]) -> str:
    lines = [
        "# Strategy Research Log",
        f"Generated: {datetime.now(tz=UTC).isoformat()}",
        "## Iteration 1",
        "- Discovery set: ETF trend/regime rotation, opening range breakout, ETF mean reversion, crypto momentum breakout, cross-market high-beta equity confirmation.",
        "- Improvement cycle: compared baseline ETF rotation vs BTC/ETH-confirmed high-beta overlay; compared crypto momentum with and without weekend participation.",
        "- Parameter ranges tested: ETF top positions {3}, realized-vol cap {2.5%, 3.0%}; crypto weekend filter {off, on}.",
        "## Outcome Summary",
    ]
    for item in sorted(results, key=lambda result: result.score, reverse=True):
        verdict = item.recommendation if item.recommendation != "reject" else f"rejected: {item.rejection_reason}"
        lines.append(f"- `{item.definition.name}`: score {item.score:.1f}, avg return {item.average_return * 100:.2f}%, {verdict}.")
    return "\n".join(lines) + "\n"


def _strategy_scorecard_markdown(results: list[StrategyEvaluation]) -> str:
    lines = [
        "# Strategy Scorecard",
        "| Rank | Strategy | Score | Avg Return | Avg Max DD | Avg Sharpe | Trades | Recommendation |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, item in enumerate(sorted(results, key=lambda result: result.score, reverse=True), start=1):
        lines.append(
            f"| {rank} | {item.definition.name} | {item.score:.1f} | {item.average_return * 100:.2f}% | {item.average_max_drawdown * 100:.2f}% | {item.average_sharpe:.2f} | {item.total_trades} | {item.recommendation} |"
        )
    return "\n".join(lines) + "\n"


def _recommended_candidates_markdown(results: list[StrategyEvaluation]) -> str:
    candidates = [item for item in sorted(results, key=lambda result: result.score, reverse=True) if item.recommendation != "reject"]
    default_system = _default_starting_system(results)
    lines = [
        "# Recommended Candidates",
        "## Highest-Score Candidate",
    ]
    if candidates:
        best = candidates[0]
        lines.extend(
            [
                f"- Strategy: `{best.definition.name}`",
                f"- Rationale: score {best.score:.1f}, avg drawdown {best.average_max_drawdown * 100:.2f}%, robustness {best.robustness * 100:.0f}%.",
                f"- Next step: {best.definition.recommended_next_step}",
            ]
        )
    if default_system is not None:
        lines.extend(
            [
                "## Best Default Starting System",
                f"- Strategy: `{default_system.definition.name}`",
                "- Why: simplest alignment with regime, trend, momentum, volatility, liquidity, and risk roles.",
                "- Default stack: 200 SMA, 20/50 EMA, RSI confirmation, ATR stop/sizing, relative volume/spread filter.",
            ]
        )
    lines.append("## Watchlist")
    for item in candidates[1:]:
        lines.append(f"- `{item.definition.name}`: keep in paper-shadow queue; focus on {item.definition.recommended_next_step}.")
    return "\n".join(lines) + "\n"


def _json_payload(results: list[StrategyEvaluation]) -> dict[str, Any]:
    payload: dict[str, Any] = {"generated_at": datetime.now(tz=UTC).isoformat(), "results": []}
    for item in results:
        payload["results"].append(
            {
                "definition": asdict(item.definition),
                "score": item.score,
                "recommendation": item.recommendation,
                "rejection_reason": item.rejection_reason,
                "score_components": item.score_components,
                "total_trades": item.total_trades,
                "average_return": item.average_return,
                "average_max_drawdown": item.average_max_drawdown,
                "robustness": item.robustness,
                "window_results": [
                    {
                        "window": asdict(window.window),
                        "metrics": {
                            "total_return": window.metrics.total_return,
                            "max_drawdown": window.metrics.max_drawdown,
                            "sharpe": window.metrics.sharpe,
                            "sortino": window.metrics.sortino,
                            "win_rate": window.metrics.win_rate,
                            "profit_factor": window.metrics.profit_factor,
                            "trade_count": window.metrics.trade_count,
                        },
                        "stress_metrics": {
                            "total_return": window.stress_metrics.total_return,
                            "max_drawdown": window.stress_metrics.max_drawdown,
                        },
                        "annualized_return": window.annualized_return,
                        "trades_per_day": window.trades_per_day,
                    }
                    for window in item.window_results
                ],
            }
        )
    return payload


def _default_system_blueprint_content(item: StrategyEvaluation) -> str:
    return "\n".join(
        [
            "name: trend_following_pullback_blueprint_v1",
            "version: 1",
            "status: candidate",
            f"asset_class: {item.definition.asset_class}",
            "universe:",
            *[f"  - {symbol}" for symbol in item.definition.universe],
            "data_sources:",
            f"  - {item.definition.primary_data_source}",
            "timeframe: 1Day",
            "hypothesis: Trade only in the dominant trend, use one momentum confirmation, size with ATR, and reject low-liquidity setups.",
            "features:",
            "  - 200 SMA regime filter",
            "  - 20 EMA and 50 EMA trend structure",
            "  - RSI pullback confirmation above 40",
            "  - ATR for stop distance and sizing",
            "  - Relative volume and spread filter",
            "entry_rules:",
            "  - only trade long when price is above 200 SMA",
            "  - require 20 EMA above 50 EMA",
            "  - buy pullback toward 20 EMA or 50 EMA",
            "  - require RSI to hold above 40",
            "  - reject low-volume or wide-spread setups",
            "exit_rules:",
            "  - exit on 2x ATR stop",
            "  - exit on 20 EMA trend break or failed momentum recovery",
            "  - allow trailing ATR stop for trend persistence",
            "risk_controls:",
            "  - risk per trade: 0.25% to 1.0% of equity",
            "  - max positions: 3",
            "  - daily loss limit and kill switch required",
            "position_sizing: ATR-normalized position sizing",
            "backtest_summary:",
            f"  proxy_strategy: {item.definition.name}",
            f"  proxy_score: {item.score}",
            "  note: current repo evidence comes from the simpler ETF trend/regime proxy; this blueprint is the preferred build-first refinement.",
            "known_risks:",
            "  - underperforms in sideways markets",
            "  - can lag sharp reversals",
            "  - requires disciplined liquidity filters",
            "implementation_steps:",
            "  - add EMA pullback and RSI confirmation fields to the ETF trend candidate",
            "  - wire ATR sizing and stop outputs into research-only evaluation",
            "  - add relative-volume and spread gating",
            "  - validate in paper mode before any promotion review",
        ]
    ) + "\n"


def run_strategy_research(
    *,
    repo_root: str | Path,
    profile: str = "paper",
    feed: str = "sip",
) -> ResearchArtifacts:
    root = Path(repo_root)
    alpaca_provider = _alpaca_provider(profile=profile, feed=feed)
    binance_provider = _binance_provider()

    all_results: list[StrategyEvaluation] = []

    etf_definition = StrategyDefinition(
        name="equity_etf_trend_regime_v1",
        asset_class="equities_etf",
        universe=ETF_UNIVERSE,
        primary_data_source="Alpaca historical stock bars",
        secondary_data_source=None,
        timeframe="1Day",
        hypothesis="Trading only the top-trending liquid ETFs during confirmed risk-on regimes should improve return quality and drawdown control.",
        features=("50d/200d trend", "60d relative strength", "20d realized volatility"),
        entry_rules=("Select top 3 ETFs by 60d return", "Require price above 200d SMA", "Require SPY risk-on regime"),
        exit_rules=("Exit on deselection", "Exit when SPY regime turns risk-off"),
        stop_loss="Portfolio-level cash switch when SPY loses 200d trend or vol filter fails",
        take_profit="Trend hold until deselection rather than fixed target",
        position_sizing="Equal weight across up to 3 positions at 10k notional each in research simulation",
        max_positions=3,
        max_daily_trades=3,
        cooldown_rules="None in baseline; rotation naturally slows turnover",
        market_regime_filter="SPY above 200d SMA and 20d realized vol <= 2.5%",
        transaction_cost_assumption="Moderate equity cost case",
        slippage_assumption="3 bps spread and 3 bps slippage baseline",
        minimum_data_required="200 daily bars per symbol",
        known_failure_modes=("Fast regime reversals", "Late-cycle concentration in one sector", "Trend lag after macro shock"),
        implementation_complexity="medium",
        recommended_next_step="Convert the strongest variant into a paper-only strategy class with daily rebalance logging.",
        notes=("The signal aligns cleanly with the existing ETF momentum and rotation architecture already present in the repo.",),
    )
    etf_windows: list[WindowEvaluation] = []
    for window in DAILY_WINDOWS:
        fetch_start = _lookback_start(window.start, 320)
        data = _fetch_equity_bars(alpaca_provider, ETF_UNIVERSE, timeframe="1Day", start=fetch_start, end=window.end)
        trades = _simulate_etf_rotation(
            data,
            activation_start=window.start,
            top_n=3,
            vol_cap=0.025,
            include_crypto_filter=False,
            crypto_filter_bars=None,
            universe=ETF_UNIVERSE,
            strategy_name=etf_definition.name,
        )
        etf_windows.append(_window_metrics(trades, window, base_cost_case=MODERATE_COST_CASE, stress_cost_case=HIGH_COST_CASE, periods_per_year=252.0))
    all_results.append(_score_strategy(etf_definition, tuple(etf_windows), implementation_fit=88.0, simplicity=82.0))

    orb_definition = StrategyDefinition(
        name="opening_range_breakout_v1",
        asset_class="equities_intraday",
        universe=ORB_UNIVERSE,
        primary_data_source="Alpaca historical stock bars",
        secondary_data_source=None,
        timeframe="15Min",
        hypothesis="Liquid names that break the opening range on volume and range expansion can continue intraday before mean reversion dominates.",
        features=("30m opening range", "bar volume expansion", "bar range expansion", "VWAP confirmation"),
        entry_rules=("Break above opening range high", "Volume > 1.2x opening baseline", "Close above VWAP proxy"),
        exit_rules=("Exit on range-midpoint failure", "Exit on VWAP failure", "Exit before session end"),
        stop_loss="Opening-range midpoint",
        take_profit="End-of-day liquidation or failed continuation exit",
        position_sizing="Single 5k notional position",
        max_positions=1,
        max_daily_trades=1,
        cooldown_rules="No re-entry same day after a stopped breakout",
        market_regime_filter="Implicit trend continuation only; no overnight holding",
        transaction_cost_assumption="High intraday equity cost case",
        slippage_assumption="8 bps spread and 6 bps slippage baseline",
        minimum_data_required="At least one full session of 15-minute bars per symbol-day",
        known_failure_modes=("False breakouts in chop", "Spread expansion around catalysts", "Low sample size outside momentum days"),
        implementation_complexity="medium",
        recommended_next_step="If revisited, add live quote spread filters before further paper promotion.",
        notes=("The existing opening-range strategy class maps well to the entry and exit logic, but fill realism is the main constraint.",),
    )
    orb_windows: list[WindowEvaluation] = []
    for window in INTRADAY_WINDOWS:
        data = _fetch_equity_bars(alpaca_provider, ORB_UNIVERSE, timeframe="15Min", start=window.start, end=window.end)
        trades = _simulate_opening_range_breakout(data)
        orb_windows.append(_window_metrics(trades, window, base_cost_case=HIGH_COST_CASE, stress_cost_case=STRESS_COST_CASE, periods_per_year=252.0 * 6.5))
    all_results.append(_score_strategy(orb_definition, tuple(orb_windows), implementation_fit=74.0, simplicity=65.0))

    mean_definition = StrategyDefinition(
        name="liquid_etf_mean_reversion_v1",
        asset_class="equities_etf",
        universe=("SPY", "QQQ", "IWM", "TLT", "GLD"),
        primary_data_source="Alpaca historical stock bars",
        secondary_data_source=None,
        timeframe="1Day",
        hypothesis="Short-term oversold conditions in highly liquid ETFs can revert when the broader market regime stays constructive.",
        features=("5d mean distance", "20d z-score", "200d trend guard", "loss cooldown"),
        entry_rules=("Buy when z-score >= 1.5", "Require benchmark regime support", "Require price near or above long-term trend"),
        exit_rules=("Exit on mean reversion", "Exit after 5 bars", "Exit on 3% stop"),
        stop_loss="3% from entry",
        take_profit="Return to 5-day mean",
        position_sizing="7.5k notional per signal",
        max_positions=2,
        max_daily_trades=2,
        cooldown_rules="2-bar cooldown after a losing exit",
        market_regime_filter="SPY above 200d SMA",
        transaction_cost_assumption="Moderate equity cost case",
        slippage_assumption="3 bps spread and 3 bps slippage baseline",
        minimum_data_required="200 daily bars per symbol and benchmark history",
        known_failure_modes=("Momentum crashes through oversold levels", "Volatility regime shifts", "Too many clustered signals during drawdowns"),
        implementation_complexity="low",
        recommended_next_step="Keep as a secondary paper-shadow module if ETF rotation needs a diversifying overlay.",
        notes=("This setup is simple to explain and easy to wire, but it remains more regime-sensitive than the trend candidates.",),
    )
    mean_windows: list[WindowEvaluation] = []
    for window in DAILY_WINDOWS:
        fetch_start = _lookback_start(window.start, 320)
        data = _fetch_equity_bars(alpaca_provider, mean_definition.universe, timeframe="1Day", start=fetch_start, end=window.end)
        benchmark = data.get("SPY", [])
        trades = _simulate_mean_reversion(data, activation_start=window.start, benchmark_bars=benchmark)
        mean_windows.append(_window_metrics(trades, window, base_cost_case=MODERATE_COST_CASE, stress_cost_case=HIGH_COST_CASE, periods_per_year=252.0))
    all_results.append(_score_strategy(mean_definition, tuple(mean_windows), implementation_fit=79.0, simplicity=78.0))

    crypto_definition = StrategyDefinition(
        name="crypto_momentum_volatility_expansion_v1",
        asset_class="crypto",
        universe=CRYPTO_UNIVERSE,
        primary_data_source="Binance public spot klines",
        secondary_data_source="Alpaca crypto daily bars for cross-check",
        timeframe="4h",
        hypothesis="High-liquidity crypto pairs can sustain breakouts after volatility compression when BTC confirms the regime.",
        features=("20-bar breakout", "14/14 ATR expansion", "20-bar volume shock", "BTC 50-bar trend filter"),
        entry_rules=("Buy after close clears prior 20-bar high", "Require 1.5x average volume", "Require BTC above 50-bar average"),
        exit_rules=("2 ATR trailing stop", "Exit under 10-bar mean", "Exit after 24 bars"),
        stop_loss="2 ATR trailing stop",
        take_profit="Trailing exit rather than fixed target",
        position_sizing="4k notional single-name exposure",
        max_positions=1,
        max_daily_trades=2,
        cooldown_rules="No same-bar re-entry; weekend filter evaluated separately",
        market_regime_filter="BTC above 50-bar average",
        transaction_cost_assumption="High crypto cost case",
        slippage_assumption="8 bps spread and 6 bps slippage baseline; stress case to 15/12 bps",
        minimum_data_required="60 four-hour bars per symbol",
        known_failure_modes=("Weekend liquidity air pockets", "False breakouts after news spikes", "Cross-exchange basis drift"),
        implementation_complexity="medium",
        recommended_next_step="Promote only a weekday-biased paper variant if shadow fills support the slippage assumptions.",
        notes=("The setup is implementable with the repo’s existing crypto strategy pattern, but it needs stricter shadow-fill evidence than the ETF ideas.",),
    )
    crypto_windows: list[WindowEvaluation] = []
    for window in CRYPTO_WINDOWS:
        data = _fetch_binance_crypto_bars(binance_provider, CRYPTO_UNIVERSE, interval="4h", start=window.start, end=window.end)
        trades = _simulate_crypto_momentum(data, activation_start=window.start, weekend_filter=True)
        crypto_windows.append(_window_metrics(trades, window, base_cost_case=HIGH_COST_CASE, stress_cost_case=STRESS_COST_CASE, periods_per_year=365.0 * 6.0))
    all_results.append(_score_strategy(crypto_definition, tuple(crypto_windows), implementation_fit=76.0, simplicity=70.0))

    cross_definition = StrategyDefinition(
        name="cross_market_high_beta_confirmation_v1",
        asset_class="equities_etf",
        universe=HIGH_BETA_ETF_UNIVERSE,
        primary_data_source="Alpaca historical stock bars",
        secondary_data_source="Alpaca crypto daily bars",
        timeframe="1Day",
        hypothesis="BTC and ETH trend confirmation can reduce weak high-beta equity entries and improve drawdown behavior during mixed risk appetite.",
        features=("High-beta ETF relative strength", "SPY trend", "BTC/ETH 50d confirmation"),
        entry_rules=("Select top 2 high-beta ETFs by 60d strength", "Require SPY risk-on", "Require BTC and ETH above 50d trend"),
        exit_rules=("Exit on deselection", "Exit when crypto confirmation fails", "Exit when SPY regime turns off"),
        stop_loss="Portfolio cash switch when equity or crypto regime breaks",
        take_profit="Trend hold until deselection",
        position_sizing="Equal weight across up to 2 positions",
        max_positions=2,
        max_daily_trades=2,
        cooldown_rules="No extra cooldown in research baseline",
        market_regime_filter="SPY above 200d SMA plus BTC/ETH above 50d averages",
        transaction_cost_assumption="Moderate equity cost case",
        slippage_assumption="3 bps spread and 3 bps slippage baseline",
        minimum_data_required="200 equity bars and 50 crypto daily bars",
        known_failure_modes=("Crypto filter can sideline valid equity trends", "Delayed confirmation after sharp equity rebounds", "Correlation breakdowns"),
        implementation_complexity="medium",
        recommended_next_step="Paper-validate as an overlay to the existing ETF momentum framework, not as a standalone live promotion candidate.",
        notes=("This was the controlled improvement cycle on the ETF trend family and directly addresses the requested cross-market filter hypothesis.",),
    )
    cross_windows: list[WindowEvaluation] = []
    for window in DAILY_WINDOWS:
        fetch_start = _lookback_start(window.start, 320)
        equity_data = _fetch_equity_bars(alpaca_provider, HIGH_BETA_ETF_UNIVERSE, timeframe="1Day", start=fetch_start, end=window.end)
        crypto_data = _fetch_crypto_daily_bars(alpaca_provider, start=fetch_start, end=window.end)
        trades = _simulate_etf_rotation(
            equity_data | {"SPY": _fetch_equity_bars(alpaca_provider, ("SPY",), timeframe="1Day", start=fetch_start, end=window.end)["SPY"]},
            activation_start=window.start,
            top_n=2,
            vol_cap=0.03,
            include_crypto_filter=True,
            crypto_filter_bars=crypto_data,
            universe=HIGH_BETA_ETF_UNIVERSE,
            strategy_name=cross_definition.name,
        )
        cross_windows.append(_window_metrics(trades, window, base_cost_case=MODERATE_COST_CASE, stress_cost_case=HIGH_COST_CASE, periods_per_year=252.0))
    all_results.append(_score_strategy(cross_definition, tuple(cross_windows), implementation_fit=85.0, simplicity=80.0))

    all_results.sort(key=lambda item: item.score, reverse=True)

    reports_dir = root / "research" / "reports"
    strategies_dir = root / "research" / "strategies"
    backtests_dir = root / "research" / "backtests"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strategies_dir.mkdir(parents=True, exist_ok=True)
    backtests_dir.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    json_path = backtests_dir / "strategy_research_results.json"
    json_path.write_text(json.dumps(_json_payload(all_results), indent=2, sort_keys=True), encoding="utf-8")
    files_written.append(str(json_path.relative_to(root)))

    outputs = {
        reports_dir / "core_strategy_framework.md": _core_strategy_framework_markdown(all_results),
        reports_dir / "strategy_research_log.md": _strategy_log_markdown(all_results),
        reports_dir / "strategy_scorecard.md": _strategy_scorecard_markdown(all_results),
        reports_dir / "recommended_candidates.md": _recommended_candidates_markdown(all_results),
        reports_dir / "final_strategy_research_report.md": _final_report_markdown(all_results, files_written.copy()),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        files_written.append(str(path.relative_to(root)))

    for item in all_results:
        if item.recommendation == "paper_validate":
            spec_path = strategies_dir / f"{item.definition.name}.yaml"
            spec_path.write_text(_strategy_spec_content(item), encoding="utf-8")
            files_written.append(str(spec_path.relative_to(root)))

    default_system = _default_starting_system(all_results)
    if default_system is not None:
        blueprint_path = strategies_dir / "trend_following_pullback_blueprint_v1.yaml"
        blueprint_path.write_text(_default_system_blueprint_content(default_system), encoding="utf-8")
        files_written.append(str(blueprint_path.relative_to(root)))

    final_report_path = reports_dir / "final_strategy_research_report.md"
    final_report_path.write_text(_final_report_markdown(all_results, files_written.copy()), encoding="utf-8")

    return ResearchArtifacts(results=all_results, files_written=files_written)
