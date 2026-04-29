#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.research.strategy_research import run_strategy_research


def main() -> int:
    parser = argparse.ArgumentParser(description="Run research-safe strategy evaluation across Alpaca and Binance data.")
    parser.add_argument("--profile", default="paper")
    parser.add_argument("--feed", default="sip")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    artifacts = run_strategy_research(repo_root=repo_root, profile=args.profile, feed=args.feed)
    summary = {
        "research_only": True,
        "live_trading_changed": False,
        "strategies_tested": [item.definition.name for item in artifacts.results],
        "top_candidate": artifacts.results[0].definition.name if artifacts.results else None,
        "files_written": artifacts.files_written,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
