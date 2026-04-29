from __future__ import annotations

import unittest

from trading_system.data.universe import AssetMetadata, UniverseCriteria, asset_passes, default_universes, filter_assets


class UniverseTests(unittest.TestCase):
    def test_filter_assets_applies_liquidity_and_spread_rules(self) -> None:
        assets = [
            AssetMetadata("GOOD", "equity", 50, 2_000_000, 100_000_000, 0.05, 2.0),
            AssetMetadata("WIDE", "equity", 50, 2_000_000, 100_000_000, 0.80, 2.0),
        ]
        result = filter_assets(assets, UniverseCriteria(max_spread_pct=0.10))
        self.assertEqual([asset.symbol for asset in result], ["GOOD"])

    def test_options_universe_requires_options_liquidity(self) -> None:
        asset = AssetMetadata(
            "AAPL",
            "equity",
            200,
            10_000_000,
            2_000_000_000,
            0.02,
            2.0,
            has_options=True,
            options_volume=10_000,
            open_interest=50_000,
        )
        passes, reasons = asset_passes(
            asset,
            UniverseCriteria(require_options=True, min_options_volume=5_000, min_open_interest=20_000),
        )
        self.assertTrue(passes, reasons)

    def test_default_universes_keep_crypto_separate(self) -> None:
        universes = default_universes()
        self.assertIn("BTC/USD", universes["crypto_major"].symbols)
        self.assertEqual(universes["crypto_major"].criteria.asset_classes, ("crypto",))


if __name__ == "__main__":
    unittest.main()

