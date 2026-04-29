#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError
from trading_system.research.backtesting.costs import BASE_COST_CASE, HIGH_COST_CASE, MODERATE_COST_CASE, STRESS_COST_CASE
from trading_system.research.backtesting.metrics import Trade, calculate_metrics
from trading_system.research.backtesting.reporting import summarize_metrics


COST_CASES = {
    "base": BASE_COST_CASE,
    "moderate": MODERATE_COST_CASE,
    "high": HIGH_COST_CASE,
    "stress": STRESS_COST_CASE,
}


def parse_symbols(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def sample_trades(symbols: list[str]) -> list[Trade]:
    trades: list[Trade] = []
    for index, symbol in enumerate(symbols):
        trades.append(
            Trade(
                symbol=symbol,
                entry_price=100.0 + index,
                exit_price=101.0 + index,
                quantity=10,
                holding_period_minutes=60,
                regime="sample",
                entry_time_of_day="sample",
            )
        )
    return trades


def provider_trades(symbols: list[str], *, start: str, end: str, profile: str, feed: str) -> list[Trade]:
    provider = CachedMarketDataProvider(
        AlpacaDataProvider(runner=CliRunner(profile=profile), feed=feed),
        DataCache("data/research_market_cache", ttl_seconds=86_400),
        default_ttl_seconds=86_400,
    )
    bars = provider.fetch_bars(tuple(symbols), "1Day", start, end)
    trades: list[Trade] = []
    for symbol in symbols:
        symbol_bars = bars.get(symbol, [])
        if len(symbol_bars) < 2:
            continue
        entry = symbol_bars[0].close
        exit_price = symbol_bars[-1].close
        if entry <= 0 or exit_price <= 0:
            continue
        trades.append(
            Trade(
                symbol=symbol,
                entry_price=entry,
                exit_price=exit_price,
                quantity=25.0 / entry,
                holding_period_minutes=max(1, len(symbol_bars) - 1) * 390,
                regime=f"{start}_{end}",
                entry_time_of_day="daily_close",
                sector="provider_backed_smoke",
            )
        )
    return trades


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only backtest metrics runner.")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--years", type=int, default=9)
    parser.add_argument("--cost-case", choices=sorted(COST_CASES), default="moderate")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--profile", default="paper")
    parser.add_argument("--feed", default="sip")
    parser.add_argument("--offline-sample", action="store_true")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols)
    provider_error = ""
    provider_backed = not args.offline_sample
    try:
        trades = sample_trades(symbols) if args.offline_sample else provider_trades(
            symbols,
            start=args.start,
            end=args.end,
            profile=args.profile,
            feed=args.feed,
        )
    except MarketDataProviderError as exc:
        provider_error = str(exc)
        provider_backed = False
        trades = sample_trades(symbols)
    metrics = calculate_metrics(trades, assumptions=COST_CASES[args.cost_case])
    print(
        json.dumps(
            {
                "strategy": args.strategy,
                "years_requested": args.years,
                "cost_case": args.cost_case,
                "provider_backed": provider_backed,
                "provider_error": provider_error,
                "period": {"start": args.start, "end": args.end},
                "live_candidate_evidence": False,
                "metrics": summarize_metrics(metrics),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
