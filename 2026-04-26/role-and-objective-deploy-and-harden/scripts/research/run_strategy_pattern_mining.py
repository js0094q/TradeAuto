#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any

from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.models import MarketBar
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError
from trading_system.research.patterns import (
    PatternObservation,
    detect_cross_sectional_rotation,
    detect_crypto_breakouts,
    detect_etf_time_series_momentum,
    detect_opening_range_breakouts,
    detect_vwap_mean_reversion,
    observations_to_dict,
    percent_change,
    summarize_observations,
)


ETF_UNIVERSE = ("SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC")
EQUITY_UNIVERSE = ("AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "V", "JPM", "UNH")
INTRADAY_UNIVERSE = ("SPY", "QQQ", "IWM", "AAPL", "NVDA")
CRYPTO_UNIVERSE = ("BTC/USD", "ETH/USD")
YAHOO_SYMBOLS = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "BTC-USD", "ETH-USD", "^VIX")
SOURCE_URLS = {
    "alpaca_cli": "https://docs.alpaca.markets/docs/market-data",
    "yahoo_chart": "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "nasdaq_earnings": "https://www.nasdaq.com/market-activity/earnings",
}


@dataclass(frozen=True)
class NasdaqEarningsEvent:
    symbol: str
    event_date: str
    event_time: str
    eps_forecast: str
    last_year_eps: str
    fiscal_quarter: str
    source: str = "nasdaq_earnings_calendar"


def iso_date_to_epoch(value: str) -> int:
    parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def yahoo_history(symbol: str, start: str, end: str) -> list[MarketBar]:
    period1 = iso_date_to_epoch(start)
    period2 = iso_date_to_epoch(end) + 86_400
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.load(response)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        return []
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    bars: list[MarketBar] = []
    for index, timestamp in enumerate(timestamps):
        try:
            close = quote["close"][index]
            open_ = quote["open"][index]
            high = quote["high"][index]
            low = quote["low"][index]
            volume = quote["volume"][index]
        except (KeyError, IndexError, TypeError):
            continue
        if None in {close, open_, high, low, volume}:
            continue
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
                vwap=None,
            )
        )
    return bars


def fetch_yahoo_histories(symbols: tuple[str, ...], start: str, end: str) -> tuple[dict[str, list[MarketBar]], list[str]]:
    output: dict[str, list[MarketBar]] = {}
    errors: list[str] = []
    for symbol in symbols:
        try:
            output[symbol] = yahoo_history(symbol, start, end)
        except Exception as exc:  # noqa: BLE001 - external source probe should continue.
            errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
        time.sleep(0.05)
    return output, errors


def nasdaq_earnings_for_date(value: date, symbols: set[str]) -> tuple[list[NasdaqEarningsEvent], str | None]:
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={value.isoformat()}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/market-activity/earnings",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.load(response)
    except Exception as exc:  # noqa: BLE001 - external source probe should continue.
        return [], f"{value.isoformat()}: {type(exc).__name__}: {exc}"
    rows = payload.get("data", {}).get("rows", [])
    events: list[NasdaqEarningsEvent] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).upper()
        if symbol not in symbols:
            continue
        events.append(
            NasdaqEarningsEvent(
                symbol=symbol,
                event_date=value.isoformat(),
                event_time=str(row.get("time", "time-not-supplied")),
                eps_forecast=str(row.get("epsForecast", "")),
                last_year_eps=str(row.get("lastYearEPS", "")),
                fiscal_quarter=str(row.get("fiscalQuarterEnding", "")),
            )
        )
    return events, None


def fetch_nasdaq_earnings(start: str, end: str, symbols: tuple[str, ...]) -> tuple[list[NasdaqEarningsEvent], list[str]]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    wanted = {symbol.upper() for symbol in symbols}
    events: list[NasdaqEarningsEvent] = []
    errors: list[str] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            daily_events, error = nasdaq_earnings_for_date(current, wanted)
            events.extend(daily_events)
            if error:
                errors.append(error)
        current += timedelta(days=1)
        time.sleep(0.03)
    return events, errors


def find_bar_index_on_or_after(bars: list[MarketBar], target_date: str) -> int | None:
    for index, bar in enumerate(bars):
        if bar.timestamp[:10] >= target_date:
            return index
    return None


def detect_post_earnings_patterns(
    bars_by_symbol: dict[str, list[MarketBar]],
    events: list[NasdaqEarningsEvent],
) -> list[PatternObservation]:
    observations: list[PatternObservation] = []
    for event in events:
        bars = bars_by_symbol.get(event.symbol, [])
        index = find_bar_index_on_or_after(bars, event.event_date)
        if index is None or index < 1 or index + 5 >= len(bars):
            continue
        if "after" in event.event_time:
            entry_index = min(index + 1, len(bars) - 6)
            entry_timing = "after-hours report: wait for next regular session and gap-hold confirmation"
        elif "pre" in event.event_time:
            entry_index = index
            entry_timing = "pre-market report: same-session gap-hold confirmation"
        else:
            entry_index = index
            entry_timing = "unknown timing: require first-session confirmation"
        previous_close = bars[entry_index - 1].close if entry_index > 0 else 0.0
        gap_pct = percent_change(previous_close, bars[entry_index].open)
        if gap_pct <= 1.0:
            continue
        observations.append(
            PatternObservation(
                strategy="post_earnings_drift_v1",
                symbol=event.symbol,
                trigger_time=bars[entry_index].timestamp,
                trigger_type="nasdaq_earnings_gap_up",
                entry_timing=entry_timing,
                forward_return_pct=percent_change(bars[entry_index].close, bars[entry_index + 5].close),
                max_adverse_move_pct=percent_change(bars[entry_index].close, min(bar.low for bar in bars[entry_index : entry_index + 6])),
                source="nasdaq_calendar_yahoo_or_alpaca_daily",
                notes=(f"gap={gap_pct:.2f}%", f"eps_forecast={event.eps_forecast}", f"fiscal_quarter={event.fiscal_quarter}"),
            )
        )
    return observations


def compare_close_sources(
    alpaca: dict[str, list[MarketBar]],
    yahoo: dict[str, list[MarketBar]],
    *,
    symbols: tuple[str, ...],
) -> dict[str, dict[str, float | int]]:
    checks: dict[str, dict[str, float | int]] = {}
    for symbol in symbols:
        alpaca_by_date = {bar.timestamp[:10]: bar.close for bar in alpaca.get(symbol, [])}
        yahoo_by_date = {bar.timestamp[:10]: bar.close for bar in yahoo.get(symbol, [])}
        diffs: list[float] = []
        for day, alpaca_close in alpaca_by_date.items():
            yahoo_close = yahoo_by_date.get(day)
            if yahoo_close is None or alpaca_close <= 0:
                continue
            diffs.append(abs(percent_change(alpaca_close, yahoo_close)))
        checks[symbol] = {
            "overlap_days": len(diffs),
            "avg_abs_close_diff_pct": fmean(diffs) if diffs else 0.0,
            "max_abs_close_diff_pct": max(diffs) if diffs else 0.0,
        }
    return checks


def markdown_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(str(item) for item in row) + " |" for row in rows)
    return "\n".join(output)


def top_observations(observations: list[PatternObservation], strategy: str, limit: int = 5) -> list[PatternObservation]:
    items = [item for item in observations if item.strategy == strategy]
    return sorted(items, key=lambda item: item.forward_return_pct, reverse=True)[:limit]


def write_reports(
    output_dir: Path,
    observations: list[PatternObservation],
    summary: dict[str, dict[str, object]],
    cross_source: dict[str, dict[str, float | int]],
    yahoo_errors: list[str],
    nasdaq_events: list[NasdaqEarningsEvent],
    nasdaq_errors: list[str],
    data_windows: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for strategy, details in sorted(summary.items()):
        rows.append(
            (
                strategy,
                details["observation_count"],
                f"{float(details['average_forward_return_pct']):.2f}%",
                f"{float(details['positive_rate']) * 100:.1f}%",
                f"{float(details['average_max_adverse_move_pct']):.2f}%",
            )
        )
    (output_dir / "strategy_pattern_observations.json").write_text(
        json.dumps(
            {
                "data_windows": data_windows,
                "source_urls": SOURCE_URLS,
                "observations": observations_to_dict(observations),
                "summary": summary,
                "cross_source_checks": cross_source,
                "nasdaq_events": [asdict(event) for event in nasdaq_events],
                "yahoo_errors": yahoo_errors,
                "nasdaq_errors": nasdaq_errors,
                "orders_placed": False,
                "live_trading_enabled": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report = [
        "# Strategy Pattern Mining",
        "",
        "This second-pass research mines read-only Alpaca historical data, Yahoo chart history, and Nasdaq earnings-calendar events for trigger patterns, entry timing, and failure modes. No order endpoints were called and live trading was not enabled.",
        "",
        markdown_table(("Strategy", "Observations", "Avg Forward Return", "Positive Rate", "Avg Max Adverse"), rows),
        "",
        "## Strategy Notes",
        "",
    ]
    for strategy in (
        "etf_time_series_momentum_v1",
        "cross_sectional_momentum_rotation_v1",
        "opening_range_breakout_v1",
        "vwap_mean_reversion_v1",
        "post_earnings_drift_v1",
        "crypto_trend_breakout_v1",
    ):
        details = summary.get(strategy, {})
        report.append(f"### {strategy}")
        if not details:
            report.append("No usable observations in this pass.")
            report.append("")
            continue
        report.append(
            f"Observed {details['observation_count']} triggers. Entry timing should remain tied to `{next(iter(details['by_trigger']))}` only after strategy-specific suppression checks pass."
        )
        samples = top_observations(observations, strategy)
        sample_rows = [
            (
                item.symbol,
                item.trigger_time[:10],
                item.trigger_type,
                item.entry_timing,
                f"{item.forward_return_pct:.2f}%",
                "; ".join(item.notes),
            )
            for item in samples
        ]
        report.append(markdown_table(("Symbol", "Date", "Trigger", "Entry Timing", "Forward Return", "Notes"), sample_rows))
        report.append("")
    report.extend(
        [
            "## Research Interpretation",
            "",
            "- ETF and cross-sectional momentum should focus on fresh alignment/rank-change events instead of continuously firing on every qualifying day.",
            "- Opening-range breakout should treat the first confirmed close outside the opening range as the candidate event and continue suppressing the first minute after open.",
            "- VWAP mean reversion needs trend-day suppression; below-VWAP stretches can continue lower before reverting.",
            "- Post-earnings drift remains event-data-limited: Nasdaq calendar supplies event timing, but surprise/revision data is still needed before promotion.",
            "- Crypto breakout remains separate because weekend/weekday and 24/7 monitoring behavior materially changes trigger risk.",
            "",
            "## Source Notes",
            "",
            f"- Alpaca historical market data: {SOURCE_URLS['alpaca_cli']}",
            f"- Yahoo chart history endpoint: {SOURCE_URLS['yahoo_chart']}",
            f"- Nasdaq earnings calendar: {SOURCE_URLS['nasdaq_earnings']}",
            "",
        ]
    )
    (output_dir / "strategy_pattern_mining.md").write_text("\n".join(report), encoding="utf-8")

    cross_rows = [
        (
            symbol,
            details["overlap_days"],
            f"{float(details['avg_abs_close_diff_pct']):.4f}%",
            f"{float(details['max_abs_close_diff_pct']):.4f}%",
        )
        for symbol, details in sorted(cross_source.items())
    ]
    (output_dir / "external_source_crosscheck.md").write_text(
        "# External Source Cross-Check\n\n"
        "Yahoo chart history was used as an external daily-price cross-check against Alpaca historical bars. Nasdaq earnings-calendar rows were used as event timing inputs for post-earnings drift research.\n\n"
        + markdown_table(("Symbol", "Overlap Days", "Avg Abs Close Diff", "Max Abs Close Diff"), cross_rows)
        + "\n\n"
        + f"Nasdaq matched earnings events: {len(nasdaq_events)}.\n\n"
        + "Yahoo errors: "
        + ("; ".join(yahoo_errors) if yahoo_errors else "none")
        + "\n\nNasdaq errors: "
        + ("; ".join(nasdaq_errors) if nasdaq_errors else "none")
        + "\n",
        encoding="utf-8",
    )

    catalog_rows = [
        (
            item.strategy,
            item.symbol,
            item.trigger_time[:16],
            item.trigger_type,
            item.entry_timing,
            f"{item.forward_return_pct:.2f}%",
            f"{item.max_adverse_move_pct:.2f}%",
            item.source,
        )
        for item in sorted(observations, key=lambda item: (item.strategy, item.trigger_time, item.symbol))[:250]
    ]
    (output_dir / "strategy_trigger_event_catalog.md").write_text(
        "# Strategy Trigger Event Catalog\n\n"
        "First 250 mined trigger events from the second-pass pattern scan. This is a research catalog only, not a trade blotter.\n\n"
        + markdown_table(
            ("Strategy", "Symbol", "Trigger Time", "Trigger Type", "Entry Timing", "Forward Return", "Adverse Move", "Source"),
            catalog_rows,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine research-only strategy patterns from Alpaca, Yahoo, and Nasdaq sources.")
    parser.add_argument("--profile", default="paper")
    parser.add_argument("--feed", default="sip")
    parser.add_argument("--daily-start", default="2018-01-01")
    parser.add_argument("--daily-end", default="2026-04-28")
    parser.add_argument("--intraday-start", default="2026-04-01T13:30:00Z")
    parser.add_argument("--intraday-end", default="2026-04-28T20:00:00Z")
    parser.add_argument("--earnings-start", default="2026-04-01")
    parser.add_argument("--earnings-end", default="2026-04-28")
    parser.add_argument("--output-dir", default="research/market_signals")
    args = parser.parse_args()

    provider = CachedMarketDataProvider(
        AlpacaDataProvider(runner=CliRunner(profile=args.profile), feed=args.feed),
        DataCache("data/research_pattern_cache", ttl_seconds=86_400),
        default_ttl_seconds=86_400,
    )
    daily_symbols = tuple(dict.fromkeys((*ETF_UNIVERSE, *EQUITY_UNIVERSE)))
    try:
        daily_bars = provider.fetch_bars(daily_symbols, "1Day", args.daily_start, args.daily_end)
    except MarketDataProviderError as exc:
        raise SystemExit(f"alpaca daily fetch failed: {exc}") from exc
    try:
        intraday_bars = provider.fetch_bars(INTRADAY_UNIVERSE, "1Min", args.intraday_start, args.intraday_end)
    except MarketDataProviderError as exc:
        raise SystemExit(f"alpaca intraday fetch failed: {exc}") from exc
    try:
        crypto_bars = provider.fetch_crypto_bars(CRYPTO_UNIVERSE, "1Day", args.daily_start, args.daily_end)
    except MarketDataProviderError as exc:
        raise SystemExit(f"alpaca crypto fetch failed: {exc}") from exc

    yahoo_bars, yahoo_errors = fetch_yahoo_histories(YAHOO_SYMBOLS, args.daily_start, args.daily_end)
    nasdaq_events, nasdaq_errors = fetch_nasdaq_earnings(args.earnings_start, args.earnings_end, EQUITY_UNIVERSE)

    observations: list[PatternObservation] = []
    observations.extend(detect_etf_time_series_momentum({symbol: daily_bars.get(symbol, []) for symbol in ETF_UNIVERSE}))
    observations.extend(detect_cross_sectional_rotation({symbol: daily_bars.get(symbol, []) for symbol in ETF_UNIVERSE}))
    observations.extend(detect_opening_range_breakouts(intraday_bars, opening_minutes=15))
    observations.extend(detect_vwap_mean_reversion(intraday_bars, stretch_pct=0.35))
    observations.extend(detect_post_earnings_patterns(daily_bars | yahoo_bars, nasdaq_events))
    observations.extend(detect_crypto_breakouts(crypto_bars))
    summary = summarize_observations(observations)
    cross_source = compare_close_sources(daily_bars, yahoo_bars, symbols=("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA"))

    write_reports(
        Path(args.output_dir),
        observations,
        summary,
        cross_source,
        yahoo_errors,
        nasdaq_events,
        nasdaq_errors,
        {
            "daily": f"{args.daily_start} to {args.daily_end}",
            "intraday": f"{args.intraday_start} to {args.intraday_end}",
            "earnings": f"{args.earnings_start} to {args.earnings_end}",
        },
    )
    print(
        json.dumps(
            {
                "orders_placed": False,
                "live_trading_enabled": False,
                "observation_count": len(observations),
                "strategies": summary,
                "nasdaq_events": len(nasdaq_events),
                "yahoo_errors": yahoo_errors,
                "nasdaq_errors": nasdaq_errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
