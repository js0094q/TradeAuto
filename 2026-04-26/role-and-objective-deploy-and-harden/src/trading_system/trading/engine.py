from __future__ import annotations

import argparse
import logging
import signal
import time

from trading_system.config import load_settings, validate_settings
from trading_system.health import readiness_payload
from trading_system.trading.live_strategy_runner import run_loop as run_live_strategy_loop


def run_engine(env_file: str | None, mode: str, *, interval_seconds: int = 900) -> int:
    settings = load_settings(env_file)
    validation = validate_settings(settings, mode=mode)
    if not validation.ok:
        logging.error("startup validation failed: %s", "; ".join(validation.errors))
        return 2
    if mode == "live":
        ready = readiness_payload(settings, external=False)
        if not ready["ok"]:
            logging.error("readiness checks failed: %s", ready)
            return 3
        logging.info("trading engine started in live strategy mode")
        return run_live_strategy_loop(env_file, interval_seconds=interval_seconds)

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    logging.info("trading engine started in %s mode", mode)
    while running:
        time.sleep(5)
    logging.info("trading engine stopped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    parser.add_argument("--mode", choices=["paper", "test", "live"], required=True)
    parser.add_argument("--interval-seconds", type=int, default=900)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run_engine(args.env_file, args.mode, interval_seconds=args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
