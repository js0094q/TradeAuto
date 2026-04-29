from __future__ import annotations

from dataclasses import replace
import unittest

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.strategies.indicators import mean_reversion_z_score
from trading_system.strategies.liquid_etf_mean_reversion import LiquidEtfMeanReversionV1
from trading_system.strategies.strategy_config import default_liquid_etf_mean_reversion_config


def enabled_strategy() -> LiquidEtfMeanReversionV1:
    return LiquidEtfMeanReversionV1(replace(default_liquid_etf_mean_reversion_config(), enabled=True))


def base_bars(prices: list[float]) -> dict[str, list[object]]:
    return {
        "SPY": bars_from_prices("SPY", trend_prices(drift=0.10)),
        "QQQ": bars_from_prices("QQQ", prices),
    }


class LiquidEtfMeanReversionTests(unittest.TestCase):
    def test_locks_tested_positive_oversold_z_score_convention(self) -> None:
        prices = trend_prices(drift=0.03, length=240) + [110.0] * 19 + [105.0]
        z_score = mean_reversion_z_score(prices, mean_window=5, z_window=20)
        self.assertGreater(z_score or 0.0, 1.5)
        result = enabled_strategy().rebalance(
            bars_by_symbol=base_bars(prices),
            quotes_by_symbol=default_quotes(("QQQ", "SPY")),
        )
        self.assertEqual([item.symbol for item in result.selected], ["QQQ"])
        self.assertEqual(result.selected[0].reason, "tested_positive_oversold_z_score")
        self.assertEqual(result.selected[0].indicators["z_score_sign_convention"], "positive_oversold_mean_5_minus_close")

    def test_exit_at_5_day_mean(self) -> None:
        prices = [100.0] * 259 + [101.0]
        result = enabled_strategy().rebalance(
            bars_by_symbol=base_bars(prices),
            quotes_by_symbol=default_quotes(("QQQ", "SPY")),
            positions_by_symbol={"QQQ": {"entry_price": 100.0, "holding_bars": 2}},
        )
        self.assertEqual(result.exits[0].reason, "returned_to_5d_mean")

    def test_exit_after_five_bars(self) -> None:
        prices = [100.0] * 255 + [99.0, 99.0, 99.0, 99.0, 98.0]
        result = enabled_strategy().rebalance(
            bars_by_symbol=base_bars(prices),
            quotes_by_symbol=default_quotes(("QQQ", "SPY")),
            positions_by_symbol={"QQQ": {"entry_price": 100.0, "holding_bars": 5}},
        )
        self.assertEqual(result.exits[0].reason, "max_holding_period_5_bars")

    def test_applies_three_percent_stop(self) -> None:
        prices = [100.0] * 259 + [96.5]
        result = enabled_strategy().rebalance(
            bars_by_symbol=base_bars(prices),
            quotes_by_symbol=default_quotes(("QQQ", "SPY")),
            positions_by_symbol={"QQQ": {"entry_price": 100.0, "holding_bars": 2}},
        )
        self.assertEqual(result.exits[0].reason, "stop_loss_3pct")

    def test_default_is_disabled_paper_shadow(self) -> None:
        strategy = LiquidEtfMeanReversionV1()
        self.assertFalse(strategy.default_enabled)
        self.assertFalse(strategy.config.enabled)
        self.assertEqual(strategy.config.mode, "paper_shadow")


if __name__ == "__main__":
    unittest.main()
