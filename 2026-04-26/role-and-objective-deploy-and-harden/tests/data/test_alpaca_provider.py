from __future__ import annotations

import json
import unittest

from trading_system.broker.alpaca_cli import CliResult
from trading_system.data.alpaca_provider import AlpacaDataProvider


class FakeRunner:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> CliResult:
        self.calls.append(args)
        return CliResult(ok=True, returncode=0, stdout=json.dumps(self.payload), stderr="")


class AlpacaDataProviderTests(unittest.TestCase):
    def test_fetch_bars_uses_current_multi_symbol_command(self) -> None:
        runner = FakeRunner(
            {
                "bars": {
                    "SPY": [
                        {
                            "t": "2026-01-02T05:00:00Z",
                            "o": 100,
                            "h": 102,
                            "l": 99,
                            "c": 101,
                            "v": 1000000,
                            "vw": 100.5,
                        }
                    ]
                }
            }
        )
        provider = AlpacaDataProvider(runner=runner, feed="sip")

        bars = provider.fetch_bars(("SPY",), "1Day", "2026-01-01", "2026-01-03")

        self.assertEqual(runner.calls[0][:3], ["data", "multi-bars", "--symbols"])
        self.assertIn("--feed", runner.calls[0])
        self.assertIn("--adjustment", runner.calls[0])
        self.assertEqual(bars["SPY"][0].close, 101.0)

    def test_latest_quote_and_snapshot_parse_current_payload_shapes(self) -> None:
        quote_runner = FakeRunner(
            {"quotes": {"SPY": {"t": "2026-01-02T20:00:00Z", "bp": 100, "ap": 100.05, "bs": 10, "as": 20}}}
        )
        quote_provider = AlpacaDataProvider(runner=quote_runner)
        quote = quote_provider.fetch_latest_quote(("SPY",))["SPY"]
        self.assertEqual(quote_runner.calls[0][1], "latest-quotes")
        self.assertEqual(quote.ask, 100.05)

        snapshot_runner = FakeRunner(
            {
                "SPY": {
                    "latestTrade": {"t": "2026-01-02T20:00:00Z", "p": 100.04},
                    "latestQuote": {"bp": 100, "ap": 100.05},
                    "dailyBar": {"v": 12345},
                }
            }
        )
        snapshot_provider = AlpacaDataProvider(runner=snapshot_runner)
        snapshot = snapshot_provider.fetch_snapshot(("SPY",))["SPY"]
        self.assertEqual(snapshot_runner.calls[0][1], "multi-snapshots")
        self.assertEqual(snapshot.volume, 12345.0)

    def test_option_chain_parses_snapshot_contracts_without_enabling_execution(self) -> None:
        runner = FakeRunner(
            {
                "snapshots": {
                    "SPY260428C00500000": {
                        "latestQuote": {"bp": 210.3, "ap": 213.21},
                        "dailyBar": {"v": 5},
                    }
                }
            }
        )
        provider = AlpacaDataProvider(runner=runner)

        chain = provider.fetch_option_chain("SPY")

        self.assertEqual(runner.calls[0][:3], ["data", "option", "chain"])
        self.assertEqual(chain.contracts[0].expiration, "2026-04-28")
        self.assertEqual(chain.contracts[0].right, "call")
        self.assertEqual(chain.contracts[0].strike, 500.0)


if __name__ == "__main__":
    unittest.main()
