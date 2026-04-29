from __future__ import annotations

import unittest
from unittest.mock import patch

from trading_system.broker.alpaca_cli import AlpacaCli
from trading_system.data.alpaca_provider import CliRunner


class Completed:
    returncode = 0
    stdout = "{}"
    stderr = ""


class AlpacaCliProfileFlagTests(unittest.TestCase):
    def test_broker_cli_places_profile_before_subcommand(self) -> None:
        with patch("trading_system.broker.alpaca_cli.subprocess.run", return_value=Completed()) as run:
            AlpacaCli(profile="paper").run("doctor")
        self.assertEqual(run.call_args.args[0][:3], ["alpaca", "--profile", "paper"])
        self.assertEqual(run.call_args.args[0][3], "doctor")
        self.assertEqual(run.call_args.kwargs["env"]["ALPACA_PROFILE"], "paper")

    def test_data_cli_places_profile_before_data_subcommand(self) -> None:
        with patch("trading_system.data.alpaca_provider.subprocess.run", return_value=Completed()) as run:
            CliRunner(profile="paper").run(["data", "multi-bars"])
        self.assertEqual(run.call_args.args[0][:3], ["alpaca", "--profile", "paper"])
        self.assertIn("data", run.call_args.args[0])
        self.assertEqual(run.call_args.args[0][-1], "--quiet")
        self.assertEqual(run.call_args.kwargs["env"]["ALPACA_PROFILE"], "paper")


if __name__ == "__main__":
    unittest.main()
