#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_system.research.focused_candidate_backtest import run_focused_candidate_backtest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run focused research-only backtests for recommended candidates.")
    parser.add_argument("--profile", default="paper")
    parser.add_argument("--feed", default="iex")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    artifacts = run_focused_candidate_backtest(repo_root=repo_root, profile=args.profile, feed=args.feed)
    print(
        json.dumps(
            {
                "research_only": True,
                "live_trading_changed": False,
                "strategies_tested": [item.strategy for item in artifacts.results],
                "files_written": artifacts.files_written,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
