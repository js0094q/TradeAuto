#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_system.research.signals.liquidity import spread_quality
from trading_system.research.signals.momentum import rate_of_change
from trading_system.research.signals.suppression import suppression_reasons
from trading_system.research.signals.trend import moving_average_trend


def parse_symbols(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only signal audit.")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    args = parser.parse_args()

    prices = [100.0 + index for index in range(60)]
    output = []
    for symbol in parse_symbols(args.symbols):
        trend = moving_average_trend(prices, short_window=10, long_window=30)
        momentum = rate_of_change(prices, window=10)
        liquidity = spread_quality(100.00, 100.05, max_spread_pct=0.25)
        suppressions = suppression_reasons(
            data_is_stale=False,
            spread_pct=float(liquidity.inputs_used.get("spread_pct", 0.0)),
            strategy_enabled=False,
        )
        output.append(
            {
                "symbol": symbol,
                "research_only": True,
                "signals": {
                    trend.name: trend.value,
                    momentum.name: momentum.value,
                    liquidity.name: liquidity.value,
                },
                "suppression_reasons": suppressions,
                "would_place_order": False,
            }
        )
    print(json.dumps({"signal_audit": output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

