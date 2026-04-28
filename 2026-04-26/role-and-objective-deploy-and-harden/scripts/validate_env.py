#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.config import load_settings, validate_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate trading-system environment safety gates.")
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--mode", choices=["diagnostics", "test", "paper", "live"], required=True)
    args = parser.parse_args()

    settings = load_settings(args.env_file)
    result = validate_settings(settings, mode=args.mode)
    for warning in result.warnings:
        print(f"warning: {warning}")
    if not result.ok:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"environment validation passed for {args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

