#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_system.research.backtesting.walk_forward import build_walk_forward_windows


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only walk-forward window builder.")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--observations", type=int, default=252 * 9)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--test-size", type=int, default=63)
    args = parser.parse_args()

    windows = build_walk_forward_windows(
        list(range(args.observations)),
        train_size=args.train_size,
        test_size=args.test_size,
    )
    print(
        json.dumps(
            {
                "strategy": args.strategy,
                "universe": args.universe,
                "window_count": len(windows),
                "first_window": windows[0].__dict__,
                "last_window": windows[-1].__dict__,
                "research_only": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

