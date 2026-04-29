from __future__ import annotations

from dataclasses import replace
import unittest

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.strategies.cross_market_high_beta_confirmation import CrossMarketHighBetaConfirmationV1
from trading_system.strategies.strategy_config import default_cross_market_high_beta_confirmation_config


def high_beta_bars() -> dict[str, list[object]]:
    drifts = {
        "SPY": 0.12,
        "QQQ": 0.40,
        "IWM": 0.20,
        "XLK": 0.50,
        "XLY": 0.32,
        "XLC": 0.25,
    }
    return {symbol: bars_from_prices(symbol, trend_prices(drift=drift)) for symbol, drift in drifts.items()}


def crypto_bars(*, eth_down: bool = False) -> dict[str, list[object]]:
    eth_prices = list(reversed(trend_prices(drift=1.0, base=2_000.0))) if eth_down else trend_prices(drift=1.0, base=2_000.0)
    return {
        "BTC/USD": bars_from_prices("BTC/USD", trend_prices(drift=10.0, base=80_000.0)),
        "ETH/USD": bars_from_prices("ETH/USD", eth_prices),
    }


class CrossMarketHighBetaConfirmationTests(unittest.TestCase):
    def enabled_strategy(self) -> CrossMarketHighBetaConfirmationV1:
        return CrossMarketHighBetaConfirmationV1(replace(default_cross_market_high_beta_confirmation_config(), enabled=True))

    def test_requires_spy_and_crypto_confirmation(self) -> None:
        result = self.enabled_strategy().rebalance(
            bars_by_symbol=high_beta_bars(),
            crypto_bars_by_symbol=crypto_bars(),
            quotes_by_symbol=default_quotes(tuple(high_beta_bars())),
        )
        self.assertEqual([item.symbol for item in result.selected], ["XLK", "QQQ"])
        self.assertTrue(result.regime["btc_confirmed"])
        self.assertTrue(result.regime["eth_confirmed"])

    def test_blocks_when_crypto_confirmation_fails(self) -> None:
        result = self.enabled_strategy().rebalance(
            bars_by_symbol=high_beta_bars(),
            crypto_bars_by_symbol=crypto_bars(eth_down=True),
            quotes_by_symbol=default_quotes(tuple(high_beta_bars())),
            current_positions=("QQQ",),
        )
        self.assertFalse(result.selected)
        self.assertIn("eth_confirmation_failed", result.risk_blocks)
        self.assertEqual(result.exits[0].reason, "crypto_confirmation_failed")

    def test_default_is_disabled_paper_shadow(self) -> None:
        strategy = CrossMarketHighBetaConfirmationV1()
        self.assertFalse(strategy.default_enabled)
        self.assertFalse(strategy.config.enabled)
        self.assertEqual(strategy.config.mode, "paper_shadow")
        result = strategy.rebalance(
            bars_by_symbol=high_beta_bars(),
            crypto_bars_by_symbol=crypto_bars(),
            quotes_by_symbol=default_quotes(tuple(high_beta_bars())),
        )
        self.assertIn("strategy_disabled", result.risk_blocks)
        self.assertFalse(result.orders)


if __name__ == "__main__":
    unittest.main()
