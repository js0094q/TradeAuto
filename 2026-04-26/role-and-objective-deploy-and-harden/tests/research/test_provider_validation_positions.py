from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from trading_system.broker.alpaca_cli import CliResult
from trading_system.research.backtesting.metrics import Trade


def load_provider_validation_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "research" / "run_provider_validation.py"
    spec = importlib.util.spec_from_file_location("run_provider_validation", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load run_provider_validation module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProviderValidationPositionTests(unittest.TestCase):
    def test_strategy_symbol_index_normalizes_symbols(self) -> None:
        module = load_provider_validation_module()
        runs = {
            "crypto_trend_breakout_v1": module.ProviderRun(
                strategy="crypto_trend_breakout_v1",
                trades=(),
                periods_tested=(),
                symbols_tested=("BTC/USD", "ETH/USD"),
                notes=(),
            ),
            "etf_time_series_momentum_v1": module.ProviderRun(
                strategy="etf_time_series_momentum_v1",
                trades=(),
                periods_tested=(),
                symbols_tested=("SPY",),
                notes=(),
            ),
        }
        index = module.strategy_symbol_index(runs)
        self.assertEqual(index["BTCUSD"], ("crypto_trend_breakout_v1",))
        self.assertEqual(index["SPY"], ("etf_time_series_momentum_v1",))

    def test_fetch_paper_positions_snapshot_infers_strategy_usage(self) -> None:
        module = load_provider_validation_module()
        payload = json.dumps(
            [
                {
                    "symbol": "QQQ",
                    "qty": "5",
                    "market_value": "1000",
                    "avg_entry_price": "199",
                    "current_price": "200",
                    "side": "long",
                    "asset_class": "us_equity",
                }
            ]
        )

        class FakeCli:
            def __init__(self, profile: str, binary: str = "alpaca") -> None:
                self.profile = profile
                self.calls: list[tuple[str, ...]] = []

            def run(self, *args: str, timeout: int = 30) -> CliResult:
                self.calls.append(args)
                if args[0] == "position":
                    return CliResult(ok=True, returncode=0, stdout=payload, stderr="")
                return CliResult(ok=False, returncode=1, stdout="", stderr="unknown command")

        original_cli = module.AlpacaCli
        module.AlpacaCli = FakeCli
        try:
            runs = {
                "etf_time_series_momentum_v1": module.ProviderRun(
                    strategy="etf_time_series_momentum_v1",
                    trades=(Trade("QQQ", 100.0, 101.0, 1.0, holding_period_minutes=390),),
                    periods_tested=("recent",),
                    symbols_tested=("QQQ", "SPY"),
                    notes=(),
                ),
            }
            positions, error = module.fetch_paper_positions_snapshot(profile="paper", runs=runs)
        finally:
            module.AlpacaCli = original_cli

        self.assertIsNone(error)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "QQQ")
        self.assertEqual(positions[0].matched_strategies, ("etf_time_series_momentum_v1",))


if __name__ == "__main__":
    unittest.main()
