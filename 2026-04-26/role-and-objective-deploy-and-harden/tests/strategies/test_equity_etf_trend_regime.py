from __future__ import annotations

from dataclasses import replace
import unittest

from tests.strategies.helpers import bars_from_prices, default_quotes, trend_prices
from trading_system.strategies.equity_etf_trend_regime import EquityEtfTrendRegimeV1
from trading_system.strategies.strategy_config import default_equity_etf_trend_regime_config, validate_strategy_config
from trading_system.telegram.strategy_alerts import format_rebalance_alert


def equity_bars() -> dict[str, list[object]]:
    drifts = {
        "SPY": 0.12,
        "QQQ": 0.42,
        "IWM": 0.18,
        "DIA": 0.10,
        "XLK": 0.50,
        "XLF": 0.08,
        "XLE": 0.05,
        "XLV": 0.11,
        "XLY": 0.34,
        "XLP": 0.07,
        "TLT": 0.03,
        "GLD": 0.09,
    }
    return {symbol: bars_from_prices(symbol, trend_prices(drift=drift)) for symbol, drift in drifts.items()}


class EquityEtfTrendRegimeTests(unittest.TestCase):
    def test_selects_top_three_and_produces_dashboard_payload(self) -> None:
        strategy = EquityEtfTrendRegimeV1()
        bars = equity_bars()
        result = strategy.rebalance(
            bars_by_symbol=bars,
            quotes_by_symbol=default_quotes(tuple(bars)),
            current_positions=("XLE",),
            portfolio_value=100_000.0,
        )
        self.assertEqual([item.symbol for item in result.selected], ["XLK", "QQQ", "XLY"])
        self.assertEqual({item.target_weight for item in result.selected}, {0.25})
        self.assertEqual(result.exits[0].symbol, "XLE")
        self.assertEqual(result.exits[0].reason, "deselected")
        payload = result.to_dashboard_payload()
        self.assertEqual(payload["strategy_name"], "equity_etf_trend_regime_v1")
        self.assertIn("rankings", payload)
        self.assertIn("indicator_snapshot", payload)
        self.assertIn("Selected: XLK 25.0%", format_rebalance_alert(result))

    def test_blocks_when_spy_is_below_200_sma(self) -> None:
        bars = equity_bars()
        bars["SPY"] = bars_from_prices("SPY", list(reversed(trend_prices(drift=0.12))))
        result = EquityEtfTrendRegimeV1().rebalance(
            bars_by_symbol=bars,
            quotes_by_symbol=default_quotes(tuple(bars)),
            current_positions=("QQQ",),
        )
        self.assertFalse(result.selected)
        self.assertIn("regime_filter_failed", result.risk_blocks)
        self.assertEqual(result.exits[0].reason, "regime_failed_cash_switch")

    def test_blocks_when_spy_realized_volatility_is_too_high(self) -> None:
        bars = equity_bars()
        volatile = trend_prices(drift=0.20)
        for index in range(235, 260):
            volatile[index] = 150.0 if index % 2 == 0 else 110.0
        bars["SPY"] = bars_from_prices("SPY", volatile)
        result = EquityEtfTrendRegimeV1().rebalance(
            bars_by_symbol=bars,
            quotes_by_symbol=default_quotes(tuple(bars)),
        )
        self.assertFalse(result.selected)
        self.assertIn("regime_filter_failed", result.risk_blocks)

    def test_live_orders_are_disabled_by_default(self) -> None:
        result = EquityEtfTrendRegimeV1().rebalance(
            bars_by_symbol=equity_bars(),
            quotes_by_symbol=default_quotes(tuple(equity_bars())),
            mode="live",
        )
        self.assertFalse(result.selected)
        self.assertIn("live_orders_disabled", result.risk_blocks)

    def test_missing_spread_blocks_when_required_and_warns_when_optional(self) -> None:
        required = EquityEtfTrendRegimeV1().rebalance(bars_by_symbol=equity_bars(), quotes_by_symbol={})
        self.assertFalse(required.selected)
        self.assertTrue(any("spread_quote_unavailable" in item.risk_blocks for item in required.rankings))

        config = replace(default_equity_etf_trend_regime_config(), liquidity=replace(default_equity_etf_trend_regime_config().liquidity, require_spread_filter=False))
        optional = EquityEtfTrendRegimeV1(config).rebalance(bars_by_symbol=equity_bars(), quotes_by_symbol={})
        self.assertTrue(optional.selected)
        self.assertTrue(optional.warnings)

    def test_default_config_is_loadable_and_validated(self) -> None:
        config = default_equity_etf_trend_regime_config()
        self.assertTrue(config.enabled)
        self.assertEqual(validate_strategy_config(config), ())


if __name__ == "__main__":
    unittest.main()
