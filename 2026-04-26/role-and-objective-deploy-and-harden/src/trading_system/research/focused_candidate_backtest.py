from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from trading_system.data.models import MarketBar
from trading_system.research.backtesting.costs import HIGH_COST_CASE, MODERATE_COST_CASE
from trading_system.research.backtesting.metrics import Trade
from trading_system.research.strategy_research import (
    DAILY_WINDOWS,
    ETF_UNIVERSE,
    HIGH_BETA_ETF_UNIVERSE,
    ResearchWindow,
    WindowEvaluation,
    _alpaca_provider,
    _annualized_return,
    _bars_by_day,
    _day_key,
    _fetch_crypto_daily_bars,
    _fetch_equity_bars,
    _lookback_start,
    _percent_change,
    _realized_volatility,
    _simulate_etf_rotation,
    _sma,
    _window_metrics,
)


@dataclass(frozen=True)
class FocusedCandidateResult:
    strategy: str
    role: str
    variant: str
    recommendation: str
    conclusion: str
    total_trades: int
    average_return: float
    annualized_return: float
    average_max_drawdown: float
    robustness: float
    average_sharpe: float
    average_profit_factor: float
    average_stress_return_delta: float
    window_results: tuple[WindowEvaluation, ...]


@dataclass(frozen=True)
class FocusedCandidateArtifacts:
    results: tuple[FocusedCandidateResult, ...]
    files_written: tuple[str, ...]


def _ema(values: list[float], window: int) -> float:
    if window <= 0 or len(values) < window:
        return 0.0
    alpha = 2.0 / (window + 1.0)
    ema = statistics.fmean(values[:window])
    for value in values[window:]:
        ema = value * alpha + ema * (1.0 - alpha)
    return ema


def _rsi(values: list[float], window: int = 14) -> float:
    if window <= 0 or len(values) <= window:
        return 0.0
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    sample = changes[-window:]
    gains = [max(change, 0.0) for change in sample]
    losses = [abs(min(change, 0.0)) for change in sample]
    average_loss = statistics.fmean(losses) if losses else 0.0
    if average_loss == 0.0:
        return 100.0 if any(gain > 0.0 for gain in gains) else 50.0
    rs = statistics.fmean(gains) / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _true_range(current: MarketBar, previous_close: float) -> float:
    return max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close))


def _atr(bars: list[MarketBar], window: int = 14) -> float:
    if len(bars) <= window:
        return 0.0
    ranges = [_true_range(bars[index], bars[index - 1].close) for index in range(len(bars) - window, len(bars))]
    return statistics.fmean(ranges) if ranges else 0.0


def _relative_volume(bars: list[MarketBar], window: int = 20) -> float:
    if len(bars) <= window:
        return 0.0
    baseline = statistics.fmean(bar.volume for bar in bars[-window - 1:-1])
    return 0.0 if baseline <= 0.0 else bars[-1].volume / baseline


def _atr_sized_quantity(entry_price: float, atr: float, *, risk_dollars: float = 250.0, notional_cap: float = 10_000.0) -> float:
    if entry_price <= 0.0:
        return 0.0
    notional_quantity = notional_cap / entry_price
    if atr <= 0.0:
        return notional_quantity
    risk_quantity = risk_dollars / max(2.0 * atr, 0.01)
    return max(0.0, min(notional_quantity, risk_quantity))


def _aligned_bars(bar_map: dict[str, MarketBar], dates: list[str], end_index: int) -> list[MarketBar]:
    return [bar_map[day] for day in dates[: end_index + 1] if day in bar_map]


def _simulate_default_stack_rotation(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    activation_start: str,
    universe: tuple[str, ...],
    strategy_name: str,
    top_n: int = 3,
    vol_cap: float = 0.025,
    min_relative_volume: float = 0.80,
    min_rsi: float = 40.0,
) -> list[Trade]:
    if "SPY" not in bars_by_symbol:
        return []

    base_dates = [_day_key(bar) for bar in bars_by_symbol["SPY"]]
    bar_maps = {symbol: _bars_by_day(symbol_bars) for symbol, symbol_bars in bars_by_symbol.items()}
    positions: dict[str, tuple[str, float, int, float]] = {}
    trades: list[Trade] = []

    for index in range(200, len(base_dates) - 1):
        day = base_dates[index]
        next_day = base_dates[index + 1]
        spy_history = [bar_maps["SPY"][current].close for current in base_dates[: index + 1] if current in bar_maps["SPY"]]
        if len(spy_history) < 200:
            continue

        regime_on = spy_history[-1] > _sma(spy_history, 200) and _realized_volatility(spy_history, 20) <= vol_cap
        rankings: list[tuple[float, str, float, float]] = []
        for symbol in universe:
            symbol_map = bar_maps.get(symbol, {})
            if day not in symbol_map or next_day not in symbol_map:
                continue
            aligned = _aligned_bars(symbol_map, base_dates, index)
            if len(aligned) < 200:
                continue
            closes = [bar.close for bar in aligned]
            if closes[-1] <= _sma(closes, 200):
                continue
            if _ema(closes, 20) <= _ema(closes, 50):
                continue
            if _rsi(closes, 14) < min_rsi:
                continue
            relative_volume = _relative_volume(aligned, 20)
            if relative_volume < min_relative_volume:
                continue
            realized_vol = max(_realized_volatility(closes, 20), 0.001)
            sixty_day_return = _percent_change(closes[-61], closes[-1])
            rankings.append((sixty_day_return / realized_vol, symbol, relative_volume, _atr(aligned, 14)))

        rankings.sort(reverse=True)
        desired = {symbol for _, symbol, _, _ in rankings[:top_n]} if regime_on and day >= activation_start else set()

        for symbol, (entry_day, entry_price, entry_index, stop_price) in list(positions.items()):
            symbol_map = bar_maps.get(symbol, {})
            current_bar = symbol_map.get(day)
            exit_bar = symbol_map.get(next_day)
            if current_bar is None or exit_bar is None:
                continue
            aligned = _aligned_bars(symbol_map, base_dates, index)
            closes = [bar.close for bar in aligned]
            trend_broken = len(closes) >= 50 and closes[-1] < _ema(closes, 50)
            stop_hit = current_bar.low <= stop_price
            if symbol in desired and not trend_broken and not stop_hit:
                continue
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_price=entry_price,
                    exit_price=exit_bar.open,
                    quantity=_atr_sized_quantity(entry_price, max((entry_price - stop_price) / 2.0, 0.0)),
                    holding_period_minutes=max(390.0, (index - entry_index + 1) * 390.0),
                    regime=strategy_name,
                    entry_time_of_day="daily_open",
                    sector="default_stack_rotation",
                )
            )
            del positions[symbol]

        atr_by_symbol = {symbol: atr for _, symbol, _, atr in rankings}
        for symbol in desired:
            if symbol in positions:
                continue
            entry_bar = bar_maps.get(symbol, {}).get(next_day)
            if entry_bar is None:
                continue
            atr = atr_by_symbol.get(symbol, 0.0)
            stop_price = entry_bar.open - 2.0 * atr if atr > 0.0 else entry_bar.open * 0.96
            positions[symbol] = (next_day, entry_bar.open, index + 1, stop_price)

    last_day = base_dates[-1]
    for symbol, (_, entry_price, entry_index, stop_price) in list(positions.items()):
        last_bar = bar_maps.get(symbol, {}).get(last_day)
        if last_bar is None:
            continue
        trades.append(
            Trade(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=last_bar.close,
                quantity=_atr_sized_quantity(entry_price, max((entry_price - stop_price) / 2.0, 0.0)),
                holding_period_minutes=max(390.0, (len(base_dates) - entry_index) * 390.0),
                regime=strategy_name,
                entry_time_of_day="daily_open",
                sector="default_stack_rotation",
            )
        )
    return trades


def _profit_factor_value(value: float) -> float:
    if math.isinf(value):
        return 3.0
    return max(0.0, min(value, 3.0))


def _focused_result(
    *,
    strategy: str,
    role: str,
    variant: str,
    window_results: tuple[WindowEvaluation, ...],
    preferred_overlay: bool = False,
) -> FocusedCandidateResult:
    total_trades = sum(item.metrics.trade_count for item in window_results)
    average_return = statistics.fmean(item.metrics.total_return for item in window_results)
    average_max_drawdown = statistics.fmean(item.metrics.max_drawdown for item in window_results)
    average_sharpe = statistics.fmean(item.metrics.sharpe for item in window_results)
    average_profit_factor = statistics.fmean(_profit_factor_value(item.metrics.profit_factor) for item in window_results)
    average_stress_delta = statistics.fmean(item.stress_return_delta for item in window_results)
    robustness = sum(1 for item in window_results if item.metrics.total_return > 0.0) / max(len(window_results), 1)
    annualized_return = statistics.fmean(
        _annualized_return(item.metrics.total_return, item.window.start, item.window.end)
        for item in window_results
    )
    if total_trades < 6:
        recommendation = "reject"
        conclusion = "Insufficient sample for paper validation."
    elif (
        average_return > 0.0
        and average_max_drawdown <= 0.03
        and robustness >= 0.75
        and average_sharpe > 0.0
        and average_profit_factor >= 1.10
    ):
        recommendation = "paper_validate"
        conclusion = "Eligible for paper-shadow validation only; no live promotion implied."
    else:
        recommendation = "watchlist"
        conclusion = "Keep in the research queue until more windows show positive net returns."
    if role == "default stack refinement" and recommendation == "watchlist":
        conclusion = "Keep the indicator stack as an implementation blueprint, but do not replace the simpler baseline until robustness improves."
    if preferred_overlay and recommendation == "paper_validate":
        conclusion = "Paper-validate only as an overlay on the ETF momentum stack, not as a standalone system."
    return FocusedCandidateResult(
        strategy=strategy,
        role=role,
        variant=variant,
        recommendation=recommendation,
        conclusion=conclusion,
        total_trades=total_trades,
        average_return=average_return,
        annualized_return=annualized_return,
        average_max_drawdown=average_max_drawdown,
        robustness=robustness,
        average_sharpe=average_sharpe,
        average_profit_factor=average_profit_factor,
        average_stress_return_delta=average_stress_delta,
        window_results=window_results,
    )


def _result_to_json(result: FocusedCandidateResult) -> dict[str, object]:
    payload = asdict(result)
    payload["window_results"] = [
        {
            "window": asdict(item.window),
            "metrics": {
                "total_return": item.metrics.total_return,
                "max_drawdown": item.metrics.max_drawdown,
                "sharpe": item.metrics.sharpe,
                "sortino": item.metrics.sortino,
                "win_rate": item.metrics.win_rate,
                "profit_factor": item.metrics.profit_factor,
                "trade_count": item.metrics.trade_count,
            },
            "stress_metrics": {
                "total_return": item.stress_metrics.total_return,
                "max_drawdown": item.stress_metrics.max_drawdown,
            },
            "annualized_return": item.annualized_return,
            "trades_per_day": item.trades_per_day,
            "stress_return_delta": item.stress_return_delta,
        }
        for item in result.window_results
    ]
    return payload


def _markdown(results: tuple[FocusedCandidateResult, ...], *, profile: str, feed: str) -> str:
    lines = [
        "# Focused Candidate Backtest",
        f"Generated: {datetime.now(tz=UTC).isoformat()}",
        "",
        "## Scope",
        "- Research-only continuation for `equity_etf_trend_regime_v1` and `cross_market_high_beta_confirmation_v1`.",
        "- No order submission, broker execution, risk limits, or live-trading gates were changed.",
        f"- Data path: Alpaca CLI profile `{profile}` using `{feed}` equity feed; Alpaca crypto daily bars for BTC/ETH confirmation.",
        "- Cost path: moderate equity costs with high-cost stress re-checks.",
        "",
        "## Results",
        "| Strategy | Role | Variant | Trades | Avg Return | Avg Ann. Return | Avg Max DD | Robustness | Stress Delta | Recommendation |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            f"| `{item.strategy}` | {item.role} | {item.variant} | {item.total_trades} | "
            f"{item.average_return * 100:.2f}% | {item.annualized_return * 100:.2f}% | "
            f"{item.average_max_drawdown * 100:.2f}% | {item.robustness * 100:.0f}% | "
            f"{item.average_stress_return_delta * 100:.2f}% | `{item.recommendation}` |"
        )
    lines.extend(["", "## Conclusions"])
    for item in results:
        lines.append(f"- `{item.strategy}` ({item.variant}): {item.conclusion}")
    lines.extend(
        [
            "",
            "## Window Detail",
        ]
    )
    for item in results:
        lines.extend(
            [
                f"### {item.strategy} - {item.variant}",
                "| Window | Period | Return | Max DD | Sharpe | Profit Factor | Trades | Stress Return |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for window in item.window_results:
            profit_factor = "inf" if math.isinf(window.metrics.profit_factor) else f"{window.metrics.profit_factor:.2f}"
            lines.append(
                f"| {window.window.name} | {window.window.start} to {window.window.end} | "
                f"{window.metrics.total_return * 100:.2f}% | {window.metrics.max_drawdown * 100:.2f}% | "
                f"{window.metrics.sharpe:.2f} | {profit_factor} | {window.metrics.trade_count} | "
                f"{window.stress_metrics.total_return * 100:.2f}% |"
            )
    lines.extend(
        [
            "",
            "## Paper Validation Gate",
            "- Treat `equity_etf_trend_regime_v1` as the default build-first system only after paper-shadow daily rebalance logs exist.",
            "- Treat `cross_market_high_beta_confirmation_v1` as an overlay candidate; it should suppress or permit high-beta ETF exposure but should not independently promote live orders.",
            "- Add live quote spread checks before any intraday or restricted-live promotion review.",
        ]
    )
    return "\n".join(lines) + "\n"


def _windowed_metrics(trades: list[Trade], window: ResearchWindow) -> WindowEvaluation:
    return _window_metrics(
        trades,
        window,
        base_cost_case=MODERATE_COST_CASE,
        stress_cost_case=HIGH_COST_CASE,
        periods_per_year=252.0,
    )


def run_focused_candidate_backtest(
    *,
    repo_root: str | Path,
    profile: str = "paper",
    feed: str = "iex",
) -> FocusedCandidateArtifacts:
    root = Path(repo_root)
    provider = _alpaca_provider(profile=profile, feed=feed)
    baseline_windows: list[WindowEvaluation] = []
    default_stack_windows: list[WindowEvaluation] = []
    overlay_windows: list[WindowEvaluation] = []

    for window in DAILY_WINDOWS:
        fetch_start = _lookback_start(window.start, 320)
        equity_data = _fetch_equity_bars(provider, ETF_UNIVERSE, timeframe="1Day", start=fetch_start, end=window.end)

        baseline_trades = _simulate_etf_rotation(
            equity_data,
            activation_start=window.start,
            top_n=3,
            vol_cap=0.025,
            include_crypto_filter=False,
            crypto_filter_bars=None,
            universe=ETF_UNIVERSE,
            strategy_name="equity_etf_trend_regime_v1",
        )
        baseline_windows.append(_windowed_metrics(baseline_trades, window))

        default_stack_trades = _simulate_default_stack_rotation(
            equity_data,
            activation_start=window.start,
            universe=ETF_UNIVERSE,
            strategy_name="equity_etf_trend_regime_v1",
        )
        default_stack_windows.append(_windowed_metrics(default_stack_trades, window))

        crypto_data = _fetch_crypto_daily_bars(provider, start=fetch_start, end=window.end)
        high_beta_data = {
            symbol: equity_data[symbol]
            for symbol in HIGH_BETA_ETF_UNIVERSE
            if symbol in equity_data
        }
        if "SPY" in equity_data:
            high_beta_data["SPY"] = equity_data["SPY"]
        overlay_trades = _simulate_etf_rotation(
            high_beta_data,
            activation_start=window.start,
            top_n=2,
            vol_cap=0.03,
            include_crypto_filter=True,
            crypto_filter_bars=crypto_data,
            universe=HIGH_BETA_ETF_UNIVERSE,
            strategy_name="cross_market_high_beta_confirmation_v1",
        )
        overlay_windows.append(_windowed_metrics(overlay_trades, window))

    results = (
        _focused_result(
            strategy="equity_etf_trend_regime_v1",
            role="best default starting system",
            variant="current 200SMA + 60d rotation baseline",
            window_results=tuple(baseline_windows),
        ),
        _focused_result(
            strategy="equity_etf_trend_regime_v1",
            role="default stack refinement",
            variant="200SMA + 20/50EMA + RSI + ATR sizing + RVOL",
            window_results=tuple(default_stack_windows),
        ),
        _focused_result(
            strategy="cross_market_high_beta_confirmation_v1",
            role="highest-score overlay candidate",
            variant="high-beta ETF rotation gated by BTC/ETH 50d trend",
            window_results=tuple(overlay_windows),
            preferred_overlay=True,
        ),
    )

    backtests_dir = root / "research" / "backtests"
    reports_dir = root / "research" / "reports"
    backtests_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = backtests_dir / "focused_candidate_backtest.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(tz=UTC).isoformat(),
                "research_only": True,
                "live_trading_changed": False,
                "profile": profile,
                "feed": feed,
                "results": [_result_to_json(item) for item in results],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report_path = reports_dir / "focused_candidate_backtest.md"
    report_path.write_text(_markdown(results, profile=profile, feed=feed), encoding="utf-8")

    files_written = (str(json_path.relative_to(root)), str(report_path.relative_to(root)))
    return FocusedCandidateArtifacts(results=results, files_written=files_written)
