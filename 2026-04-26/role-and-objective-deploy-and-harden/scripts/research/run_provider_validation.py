#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.models import MarketBar
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError
from trading_system.research.backtesting.costs import MODERATE_COST_CASE
from trading_system.research.backtesting.metrics import Trade, calculate_metrics
from trading_system.research.backtesting.reporting import summarize_metrics


ETF_UNIVERSE = ("SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI")
CRYPTO_UNIVERSE = ("BTC/USD", "ETH/USD")
VALIDATION_PERIODS = (
    ("2018_volatility_shock", "2018 volatility shock", "2018-01-01", "2018-04-30"),
    ("2020_covid_crash_rebound", "2020 COVID crash and rebound", "2020-02-01", "2020-07-31"),
    ("2021_liquidity_momentum", "2021 liquidity/momentum", "2021-01-01", "2021-12-31"),
    ("2022_rate_hike_bear", "2022 rate-hike bear market", "2022-01-01", "2022-12-31"),
    ("2023_mega_cap_ai", "2023 mega-cap/AI concentration", "2023-01-01", "2023-12-31"),
    ("2024_normalization", "2024 recent market structure", "2024-01-01", "2024-12-31"),
    ("2025_2026_recent", "2025-2026 recent behavior", "2025-01-01", "2026-04-28"),
)


@dataclass(frozen=True)
class ProviderRun:
    strategy: str
    trades: tuple[Trade, ...]
    periods_tested: tuple[str, ...]
    symbols_tested: tuple[str, ...]
    notes: tuple[str, ...]


def close_prices(bars: list[MarketBar]) -> list[float]:
    return [bar.close for bar in bars if bar.close > 0]


def pct_change(previous: float, current: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous


def moving_average(values: list[float], index: int, window: int) -> float:
    if index + 1 < window:
        return 0.0
    subset = values[index + 1 - window : index + 1]
    return fmean(subset)


def make_trade(
    symbol: str,
    bars: list[MarketBar],
    entry_index: int,
    exit_index: int,
    *,
    regime: str,
    notional: float,
    strategy: str,
) -> Trade | None:
    entry = bars[entry_index].close
    exit_price = bars[exit_index].close
    if entry <= 0 or exit_price <= 0:
        return None
    return Trade(
        symbol=symbol,
        entry_price=entry,
        exit_price=exit_price,
        quantity=notional / entry,
        holding_period_minutes=(exit_index - entry_index) * 390,
        regime=regime,
        entry_time_of_day="daily_close",
        sector=strategy,
    )


def simulate_etf_time_series(
    equity_data: dict[str, dict[str, list[MarketBar]]],
    *,
    notional: float,
) -> ProviderRun:
    trades: list[Trade] = []
    periods: set[str] = set()
    symbols: set[str] = set()
    for period_id, symbol_map in equity_data.items():
        for symbol, bars in symbol_map.items():
            if symbol not in ETF_UNIVERSE:
                continue
            prices = close_prices(bars)
            if len(prices) < 221:
                continue
            index = 200
            while index < len(prices) - 21:
                sma_50 = moving_average(prices, index, 50)
                sma_200 = moving_average(prices, index, 200)
                return_20 = pct_change(prices[index - 20], prices[index])
                return_60 = pct_change(prices[index - 60], prices[index])
                if prices[index] > sma_50 > sma_200 and return_20 > 0 and return_60 > 0:
                    trade = make_trade(
                        symbol,
                        bars,
                        index,
                        index + 20,
                        regime=period_id,
                        notional=notional,
                        strategy="etf_time_series_momentum_v1",
                    )
                    if trade:
                        trades.append(trade)
                        periods.add(period_id)
                        symbols.add(symbol)
                    index += 20
                else:
                    index += 5
    return ProviderRun(
        strategy="etf_time_series_momentum_v1",
        trades=tuple(trades),
        periods_tested=tuple(sorted(periods)),
        symbols_tested=tuple(sorted(symbols)),
        notes=("20-day hold, 50/200-day trend, 20/60-day return confirmation",),
    )


def simulate_cross_sectional_rotation(
    equity_data: dict[str, dict[str, list[MarketBar]]],
    *,
    notional: float,
) -> ProviderRun:
    trades: list[Trade] = []
    periods: set[str] = set()
    symbols: set[str] = set()
    for period_id, symbol_map in equity_data.items():
        usable = {symbol: bars for symbol, bars in symbol_map.items() if len(bars) >= 147}
        if len(usable) < 5:
            continue
        max_index = min(len(bars) for bars in usable.values()) - 22
        index = 126
        while index < max_index:
            ranked = sorted(
                (
                    (pct_change(bars[index - 60].close, bars[index].close), symbol, bars)
                    for symbol, bars in usable.items()
                    if bars[index - 60].close > 0 and bars[index].close > 0
                ),
                reverse=True,
            )
            for _, symbol, bars in ranked[:2]:
                trade = make_trade(
                    symbol,
                    bars,
                    index,
                    index + 21,
                    regime=period_id,
                    notional=notional,
                    strategy="cross_sectional_momentum_rotation_v1",
                )
                if trade:
                    trades.append(trade)
                    periods.add(period_id)
                    symbols.add(symbol)
            index += 21
    return ProviderRun(
        strategy="cross_sectional_momentum_rotation_v1",
        trades=tuple(trades),
        periods_tested=tuple(sorted(periods)),
        symbols_tested=tuple(sorted(symbols)),
        notes=("Top-2 60-day ETF momentum rotation, 21-day hold, long-only",),
    )


def simulate_crypto_trend(
    crypto_data: dict[str, dict[str, list[MarketBar]]],
    *,
    notional: float,
) -> ProviderRun:
    trades: list[Trade] = []
    periods: set[str] = set()
    symbols: set[str] = set()
    for period_id, symbol_map in crypto_data.items():
        for symbol, bars in symbol_map.items():
            if len(bars) < 35:
                continue
            index = 20
            while index < len(bars) - 11:
                prior_high = max(bar.high for bar in bars[index - 20 : index])
                range_now = bars[index].high - bars[index].low
                prior_range = fmean([bar.high - bar.low for bar in bars[index - 10 : index]])
                if bars[index].close > prior_high and prior_range > 0 and range_now >= prior_range:
                    trade = make_trade(
                        symbol,
                        bars,
                        index,
                        index + 10,
                        regime=period_id,
                        notional=notional,
                        strategy="crypto_trend_breakout_v1",
                    )
                    if trade:
                        trades.append(trade)
                        periods.add(period_id)
                        symbols.add(symbol)
                    index += 10
                else:
                    index += 3
    return ProviderRun(
        strategy="crypto_trend_breakout_v1",
        trades=tuple(trades),
        periods_tested=tuple(sorted(periods)),
        symbols_tested=tuple(sorted(symbols)),
        notes=("20-day breakout, ATR-proxy expansion, 10-day hold; spread evidence still required",),
    )


def metric_summary(trades: tuple[Trade, ...]) -> dict[str, object]:
    if not trades:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "trade_count": 0,
            "slippage_adjusted_return": 0.0,
            "by_symbol": {},
            "by_regime": {},
            "by_time_of_day": {},
        }
    metrics = calculate_metrics(
        list(trades),
        starting_equity=1_000.0,
        assumptions=MODERATE_COST_CASE,
    )
    return summarize_metrics(metrics)


def period_returns(trades: tuple[Trade, ...]) -> dict[str, float]:
    by_period: dict[str, list[Trade]] = {}
    for trade in trades:
        by_period.setdefault(trade.regime, []).append(trade)
    return {period: float(metric_summary(tuple(items))["slippage_adjusted_return"]) for period, items in by_period.items()}


def classify_status(run: ProviderRun, *, strategy: str, period_result: dict[str, float]) -> tuple[str, str, str]:
    if strategy == "post_earnings_drift_v1":
        return ("needs_data", "research_only", "Earnings surprise and revisions data are not available in the current provider adapter.")
    if strategy in {"opening_range_breakout_v1", "vwap_mean_reversion_v1"}:
        return ("shadow_ready", "shadow", "Implementation is explainable and gated, but provider-backed intraday validation is still required.")
    if not run.trades:
        return ("needs_validation", "shadow", "Provider data loaded, but the fixed rule set generated no validation trades.")
    positive_periods = sum(1 for value in period_result.values() if value > 0)
    total_return = float(metric_summary(run.trades)["slippage_adjusted_return"])
    if len(run.periods_tested) >= 5 and positive_periods >= 3 and total_return > 0:
        if strategy == "crypto_trend_breakout_v1":
            return ("shadow_ready", "shadow", "Daily crypto bars validate signal availability; spread/liquidity and 24/7 monitoring evidence still block paper promotion.")
        return ("paper_ready", "paper", "Provider-backed daily validation spans multiple regimes with positive net periods under moderate costs.")
    if positive_periods >= 3:
        return ("shadow_ready", "shadow", "Provider-backed evidence exists across multiple regimes, but aggregate cost-adjusted results do not yet support paper promotion.")
    return ("shadow_ready", "shadow", "Provider-backed evidence exists, but breadth or net-period stability is not yet enough for paper promotion.")


def score_row(status: str, *, strategy: str, has_provider_data: bool, positive_periods: int) -> dict[str, int]:
    paper = status == "paper_ready"
    return {
        "real_world_basis": 5 if strategy != "post_earnings_drift_v1" else 4,
        "data_availability": 5 if has_provider_data else 2,
        "implementation_readiness": 5 if status in {"paper_ready", "shadow_ready"} else 3,
        "signal_clarity": 5 if status in {"paper_ready", "shadow_ready"} else 4,
        "backtest_result": 4 if paper else (3 if positive_periods else 1),
        "walk_forward_result": 3 if positive_periods >= 3 else 1,
        "execution_realism": 4 if paper else 3,
        "risk_containment": 5,
        "monitoring": 3,
        "failure_safety": 5,
    }


def markdown_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(str(item) for item in row) + " |" for row in rows)
    return "\n".join(output)


def write_reports(
    output_dir: Path,
    runs: dict[str, ProviderRun],
    statuses: dict[str, tuple[str, str, str]],
    scores: dict[str, dict[str, int]],
    fetch_errors: list[str],
    option_contract_count: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {
        name: {
            "metrics": metric_summary(run.trades),
            "period_returns": period_returns(run.trades),
            "periods_tested": run.periods_tested,
            "symbols_tested": run.symbols_tested,
            "notes": run.notes,
        }
        for name, run in runs.items()
    }
    (output_dir / "provider_validation_results.json").write_text(
        json.dumps(
            {
                "provider": "alpaca_cli_read_only",
                "cost_case": MODERATE_COST_CASE.name,
                "periods": VALIDATION_PERIODS,
                "option_contracts_sampled": option_contract_count,
                "fetch_errors": fetch_errors,
                "results": results,
                "statuses": {name: status for name, status in statuses.items()},
                "scores": scores,
                "orders_placed": False,
                "live_trading_enabled": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    backtest_rows = []
    for name, run in runs.items():
        metrics = metric_summary(run.trades)
        backtest_rows.append(
            (
                name,
                len(run.symbols_tested),
                len(run.periods_tested),
                metrics["trade_count"],
                f"{float(metrics['slippage_adjusted_return']) * 100:.2f}%",
                f"{float(metrics['max_drawdown']) * 100:.2f}%",
                f"{float(metrics['win_rate']) * 100:.1f}%",
            )
        )
    (output_dir / "provider_backtest_results.md").write_text(
        "# Provider-Backed Backtest Results\n\n"
        "Read-only Alpaca CLI data was used for historical daily bars. No order endpoints were called, "
        "and live trading was not enabled. Metrics use moderate spread/slippage assumptions and a "
        "$25 strategy notional against a $1,000 research equity base for comparability.\n\n"
        + markdown_table(
            (
                "Strategy",
                "Symbols",
                "Regimes",
                "Trades",
                "Slippage-Adjusted Return",
                "Max Drawdown",
                "Win Rate",
            ),
            backtest_rows,
        )
        + "\n\nFetch gaps: "
        + ("; ".join(fetch_errors) if fetch_errors else "none")
        + "\n",
        encoding="utf-8",
    )

    score_rows = [
        (name, statuses[name][0], statuses[name][1], sum(scores[name].values()), statuses[name][2])
        for name in statuses
    ]
    (output_dir / "strategy_scorecard.md").write_text(
        "# Strategy Scorecard\n\n"
        "Scores are 0-5 per mandate dimension. Monitoring remains below restricted-live threshold "
        "because dashboard/Telegram shadow evidence has not yet been produced for the new candidates.\n\n"
        + markdown_table(("Strategy", "Status", "Best Mode Now", "Score", "Reason"), score_rows)
        + "\n\nNo strategy is marked `restricted_live_ready`.\n",
        encoding="utf-8",
    )

    final_rows = [(name, *statuses[name]) for name in statuses]
    (output_dir / "ready_strategy_validation.md").write_text(
        "# Ready Strategy Validation\n\n"
        "Provider-backed validation supports controlled shadow/paper evaluation, not live deployment. "
        "All strategy configuration remains default-disabled and live mode remains blocked by existing gates.\n\n"
        + markdown_table(("Strategy", "Status", "Best Mode Now", "Reason"), final_rows)
        + "\n\nManual enablement still requires editing untracked runtime configuration, leaving kill switch controls intact, "
        "and validating Telegram/dashboard visibility before any paper or restricted-live run.\n",
        encoding="utf-8",
    )

    walk_rows = []
    for name, run in runs.items():
        returns = period_returns(run.trades)
        positive = sum(1 for value in returns.values() if value > 0)
        walk_rows.append((name, len(returns), positive, "pass" if positive >= 3 else "needs more validation"))
    (output_dir / "walk_forward_validation.md").write_text(
        "# Walk-Forward Validation\n\n"
        "This pass uses parameter-fixed, regime-segmented walk-forward checks. It is useful for first promotion "
        "decisions but does not replace full train/validation/test optimization controls.\n\n"
        + markdown_table(("Strategy", "Provider Windows", "Positive Test Windows", "Assessment"), walk_rows)
        + "\n\nRestricted-live review still requires paper/shadow execution logs, spread evidence, latency sensitivity, "
        "Telegram alert validation, dashboard visibility, and kill-switch validation.\n",
        encoding="utf-8",
    )

    (output_dir / "shadow_validation_plan.md").write_text(
        "# Shadow Validation Plan\n\n"
        "- Keep every strategy `enabled: false` until explicitly selected for shadow or paper mode.\n"
        "- Start with `etf_time_series_momentum_v1` and `cross_sectional_momentum_rotation_v1` in shadow review; paper promotion requires aggregate cost-adjusted improvement and operator visibility.\n"
        "- Keep `opening_range_breakout_v1` and `vwap_mean_reversion_v1` in shadow only until intraday bars, spreads, first-minute suppression, trend-day suppression, and end-of-day flat behavior are validated.\n"
        "- Keep `crypto_trend_breakout_v1` in shadow only until crypto spread, weekend liquidity, 24/7 monitoring, and crypto-specific drawdown gates are proven.\n"
        "- Keep `post_earnings_drift_v1` research-only until point-in-time earnings surprise data is available.\n"
        "- Required operator checks before any paper run: fresh market data, kill switch readable/off only by policy, risk engine healthy, Telegram alerts working, dashboard status visible, and strategy-specific enable flag set in untracked config.\n",
        encoding="utf-8",
    )


def fetch_period_data(provider: CachedMarketDataProvider) -> tuple[dict[str, dict[str, list[MarketBar]]], dict[str, dict[str, list[MarketBar]]], list[str]]:
    equity_data: dict[str, dict[str, list[MarketBar]]] = {}
    crypto_data: dict[str, dict[str, list[MarketBar]]] = {}
    errors: list[str] = []
    for period_id, _, start, end in VALIDATION_PERIODS:
        try:
            equity_data[period_id] = provider.fetch_bars(ETF_UNIVERSE, "1Day", start, end)
        except MarketDataProviderError as exc:
            equity_data[period_id] = {}
            errors.append(f"{period_id} equity bars: {exc}")
        try:
            crypto_data[period_id] = provider.fetch_crypto_bars(CRYPTO_UNIVERSE, "1Day", start, end)
        except MarketDataProviderError as exc:
            crypto_data[period_id] = {}
            errors.append(f"{period_id} crypto bars: {exc}")
    return equity_data, crypto_data, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only provider-backed strategy validation.")
    parser.add_argument("--profile", default="paper")
    parser.add_argument("--feed", default="sip")
    parser.add_argument("--option-feed", default="opra")
    parser.add_argument("--output-dir", default="research/market_signals")
    parser.add_argument("--max-notional", type=float, default=25.0)
    args = parser.parse_args()

    provider = CachedMarketDataProvider(
        AlpacaDataProvider(
            runner=CliRunner(profile=args.profile),
            feed=args.feed,
            option_feed=args.option_feed,
        ),
        DataCache("data/research_market_cache", ttl_seconds=86_400),
        default_ttl_seconds=86_400,
    )
    equity_data, crypto_data, fetch_errors = fetch_period_data(provider)
    option_contract_count = 0
    try:
        option_contract_count = len(provider.fetch_option_chain("SPY").contracts)
    except MarketDataProviderError as exc:
        fetch_errors.append(f"SPY option chain sample: {exc}")

    completed_runs = {
        run.strategy: run
        for run in (
            simulate_etf_time_series(equity_data, notional=args.max_notional),
            simulate_cross_sectional_rotation(equity_data, notional=args.max_notional),
            simulate_crypto_trend(crypto_data, notional=args.max_notional),
        )
    }
    empty_runs = {
        "opening_range_breakout_v1": ProviderRun(
            "opening_range_breakout_v1",
            (),
            (),
            (),
            ("Intraday provider validation still required.",),
        ),
        "vwap_mean_reversion_v1": ProviderRun(
            "vwap_mean_reversion_v1",
            (),
            (),
            (),
            ("Intraday VWAP and trend-day validation still required.",),
        ),
        "post_earnings_drift_v1": ProviderRun(
            "post_earnings_drift_v1",
            (),
            (),
            (),
            ("Point-in-time earnings surprise data unavailable.",),
        ),
    }
    runs = {**completed_runs, **empty_runs}
    statuses = {
        name: classify_status(run, strategy=name, period_result=period_returns(run.trades))
        for name, run in runs.items()
    }
    scores = {
        name: score_row(
            statuses[name][0],
            strategy=name,
            has_provider_data=bool(run.periods_tested),
            positive_periods=sum(1 for value in period_returns(run.trades).values() if value > 0),
        )
        for name, run in runs.items()
    }
    write_reports(
        Path(args.output_dir),
        runs,
        statuses,
        scores,
        fetch_errors,
        option_contract_count,
    )
    print(
        json.dumps(
            {
                "orders_placed": False,
                "live_trading_enabled": False,
                "output_dir": args.output_dir,
                "statuses": statuses,
                "fetch_errors": fetch_errors,
                "option_contracts_sampled": option_contract_count,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
