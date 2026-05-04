from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading_system.config import Settings


class BrokerUnavailable(RuntimeError):
    pass


@dataclass
class AlpacaBroker:
    settings: Settings

    def _trading_client(self) -> Any:
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise BrokerUnavailable("alpaca-py is not installed") from exc
        paper = self.settings.alpaca_base_url != "https://api.alpaca.markets"
        return TradingClient(
            self.settings.alpaca_api_key,
            self.settings.alpaca_api_secret,
            paper=paper,
        )

    def get_account(self) -> Any:
        return self._trading_client().get_account()

    def get_clock(self) -> Any:
        return self._trading_client().get_clock()

    def list_positions(self) -> Any:
        return self._trading_client().get_all_positions()

    def list_orders(self) -> Any:
        return self._trading_client().get_orders()

    def validate_connectivity(self) -> dict[str, bool]:
        account = self.get_account()
        expected_account_number = self.settings.raw.get("ALPACA_EXPECTED_ACCOUNT_NUMBER", "").strip()
        actual_account_number = str(getattr(account, "account_number", "") or "").strip()
        if expected_account_number and actual_account_number != expected_account_number:
            raise BrokerUnavailable(
                f"alpaca account mismatch: expected {expected_account_number}, got {actual_account_number or 'unknown'}"
            )
        self.get_clock()
        return {"account": True, "clock": True}
