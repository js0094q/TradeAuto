from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssetMetadata:
    symbol: str
    asset_class: str
    price: float
    average_daily_volume: float
    dollar_volume: float
    spread_pct: float
    volatility_pct: float
    exchange: str = ""
    relative_volume: float = 1.0
    options_volume: float = 0.0
    open_interest: float = 0.0
    tradable: bool = True
    has_options: bool = False


@dataclass(frozen=True)
class UniverseCriteria:
    min_price: float = 5.0
    min_average_daily_volume: float = 1_000_000.0
    min_dollar_volume: float = 25_000_000.0
    max_spread_pct: float = 0.25
    min_volatility_pct: float = 0.0
    max_volatility_pct: float = 12.0
    min_relative_volume: float = 0.0
    require_options: bool = False
    min_options_volume: float = 0.0
    min_open_interest: float = 0.0
    asset_classes: tuple[str, ...] = ("equity", "etf")
    exchanges: tuple[str, ...] = ()


@dataclass(frozen=True)
class UniverseDefinition:
    name: str
    description: str
    symbols: tuple[str, ...]
    criteria: UniverseCriteria
    assumptions: tuple[str, ...] = field(default_factory=tuple)


CORE_ETFS = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLY",
    "XLP",
    "XLU",
    "XLB",
    "XLRE",
    "XLC",
)

MEGA_CAP_LIQUID = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "TSLA",
    "AVGO",
    "JPM",
    "LLY",
    "UNH",
    "V",
    "MA",
    "XOM",
)

CRYPTO_MAJORS = ("BTC/USD", "ETH/USD", "SOL/USD")


def default_universes() -> dict[str, UniverseDefinition]:
    return {
        "core_etf": UniverseDefinition(
            name="core_etf",
            description="Liquid index and sector ETFs for regime and broad-market strategy research.",
            symbols=CORE_ETFS,
            criteria=UniverseCriteria(asset_classes=("etf",), min_dollar_volume=50_000_000.0),
        ),
        "mega_cap_liquid": UniverseDefinition(
            name="mega_cap_liquid",
            description="Highly liquid large-cap equities across sectors.",
            symbols=MEGA_CAP_LIQUID,
            criteria=UniverseCriteria(asset_classes=("equity",), min_dollar_volume=100_000_000.0),
        ),
        "high_volume_momentum": UniverseDefinition(
            name="high_volume_momentum",
            description="Rule-defined high-volume equities with liquidity, spread, volatility, and relative-volume gates.",
            symbols=(),
            criteria=UniverseCriteria(
                min_price=10.0,
                min_average_daily_volume=2_000_000.0,
                min_dollar_volume=75_000_000.0,
                max_spread_pct=0.15,
                min_volatility_pct=1.0,
                max_volatility_pct=10.0,
                min_relative_volume=1.2,
                asset_classes=("equity",),
            ),
        ),
        "options_capable_underlyings": UniverseDefinition(
            name="options_capable_underlyings",
            description="Equity underlyings where options data may be used as confirmation or suppression only.",
            symbols=(),
            criteria=UniverseCriteria(
                min_price=20.0,
                min_average_daily_volume=2_000_000.0,
                min_dollar_volume=100_000_000.0,
                max_spread_pct=0.15,
                require_options=True,
                min_options_volume=5_000.0,
                min_open_interest=20_000.0,
                asset_classes=("equity", "etf"),
            ),
        ),
        "crypto_major": UniverseDefinition(
            name="crypto_major",
            description="Supported major crypto pairs researched with 24/7 market assumptions.",
            symbols=CRYPTO_MAJORS,
            criteria=UniverseCriteria(
                min_price=1.0,
                min_average_daily_volume=0.0,
                min_dollar_volume=0.0,
                max_spread_pct=0.50,
                max_volatility_pct=20.0,
                asset_classes=("crypto",),
            ),
            assumptions=("24/7 sessions", "separate liquidity and weekend checks", "no equity market-hours reuse"),
        ),
    }


def asset_passes(asset: AssetMetadata, criteria: UniverseCriteria) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    asset_class = asset.asset_class.strip().lower()
    if asset_class not in criteria.asset_classes:
        reasons.append("asset class excluded")
    if criteria.exchanges and asset.exchange not in criteria.exchanges:
        reasons.append("exchange excluded")
    if not asset.tradable:
        reasons.append("asset not tradable by provider")
    if asset.price < criteria.min_price:
        reasons.append("price below minimum")
    if asset.average_daily_volume < criteria.min_average_daily_volume:
        reasons.append("average volume below minimum")
    if asset.dollar_volume < criteria.min_dollar_volume:
        reasons.append("dollar volume below minimum")
    if asset.spread_pct > criteria.max_spread_pct:
        reasons.append("spread above maximum")
    if asset.volatility_pct < criteria.min_volatility_pct:
        reasons.append("volatility below minimum")
    if asset.volatility_pct > criteria.max_volatility_pct:
        reasons.append("volatility above maximum")
    if asset.relative_volume < criteria.min_relative_volume:
        reasons.append("relative volume below minimum")
    if criteria.require_options and not asset.has_options:
        reasons.append("options unavailable")
    if asset.options_volume < criteria.min_options_volume:
        reasons.append("options volume below minimum")
    if asset.open_interest < criteria.min_open_interest:
        reasons.append("open interest below minimum")
    return not reasons, tuple(reasons)


def filter_assets(assets: list[AssetMetadata], criteria: UniverseCriteria) -> list[AssetMetadata]:
    return [asset for asset in assets if asset_passes(asset, criteria)[0]]

