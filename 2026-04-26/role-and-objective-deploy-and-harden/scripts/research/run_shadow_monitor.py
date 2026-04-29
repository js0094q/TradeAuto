#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trading_system.data.stream_health import StreamHealthMonitor
from trading_system.research.realtime.stream_monitor import ResearchStreamMonitor


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only shadow monitor launcher.")
    parser.add_argument("--universe", required=True)
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    monitor = ResearchStreamMonitor(StreamHealthMonitor())
    monitor.on_connect()
    monitor.on_heartbeat()
    status = monitor.status()
    print(
        json.dumps(
            {
                "universe": args.universe,
                "duration_minutes": args.duration_minutes,
                "dry_run": args.dry_run,
                "research_only": True,
                "would_place_orders": False,
                "stream_health": status.__dict__,
                "note": "Connect provider WebSocket here only after credentials and storage target are configured.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

