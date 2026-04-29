from __future__ import annotations

from collections.abc import Mapping

from trading_system.data.alpaca_market_data import (
    MarketDataProviderError as ResearchDataError,
    MarketDataRequest,
    ReadOnlyAlpacaMarketData,
)
from trading_system.data.alpaca_provider import AlpacaDataProvider, CliRunner
from trading_system.data.models import MarketBar
from trading_system.data.provider import CachedMarketDataProvider, DataCache, MarketDataProviderError


def _to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_market_bar(symbol: str, item: object) -> MarketBar | None:
    if isinstance(item, MarketBar):
        return item
    if not isinstance(item, Mapping):
        return None
    timestamp = str(item.get("timestamp") or item.get("t") or "")
    if not timestamp:
        return None
    raw_vwap = item.get("vwap", item.get("vw"))
    vwap = _to_float(raw_vwap) if raw_vwap is not None else None
    return MarketBar(
        symbol=symbol,
        timestamp=timestamp,
        open=_to_float(item.get("open", item.get("o", 0.0))),
        high=_to_float(item.get("high", item.get("h", 0.0))),
        low=_to_float(item.get("low", item.get("l", 0.0))),
        close=_to_float(item.get("close", item.get("c", 0.0))),
        volume=_to_float(item.get("volume", item.get("v", 0.0))),
        vwap=vwap,
    )


def _normalize_records(symbols: tuple[str, ...], records: Mapping[str, object]) -> dict[str, list[MarketBar]]:
    output: dict[str, list[MarketBar]] = {}
    for symbol in symbols:
        raw_items = records.get(symbol, [])
        if not isinstance(raw_items, list):
            output[symbol] = []
            continue
        bars = [bar for bar in (_as_market_bar(symbol, item) for item in raw_items) if bar is not None]
        output[symbol] = bars
    return output


def build_read_only_historical_data_layer(
    *,
    profile: str,
    feed: str,
    option_feed: str = "opra",
    cache_root: str = "data/research_market_cache",
    cache_ttl_seconds: float = 86_400.0,
) -> tuple[ReadOnlyAlpacaMarketData, CachedMarketDataProvider]:
    provider = CachedMarketDataProvider(
        AlpacaDataProvider(
            runner=CliRunner(profile=profile),
            feed=feed,
            option_feed=option_feed,
        ),
        DataCache(cache_root, ttl_seconds=cache_ttl_seconds),
        default_ttl_seconds=cache_ttl_seconds,
    )

    def fetcher(request: MarketDataRequest) -> Mapping[str, object]:
        try:
            if request.asset_class.lower() == "crypto":
                return provider.fetch_crypto_bars(request.symbols, request.timeframe, request.start, request.end)
            return provider.fetch_bars(request.symbols, request.timeframe, request.start, request.end)
        except MarketDataProviderError as exc:
            raise ResearchDataError(str(exc)) from exc

    return (
        ReadOnlyAlpacaMarketData(
            fetcher=fetcher,
            source="alpaca_historical_research_layer",
        ),
        provider,
    )


def fetch_historical_bars(
    data_layer: ReadOnlyAlpacaMarketData,
    *,
    symbols: tuple[str, ...],
    asset_class: str,
    timeframe: str,
    start: str,
    end: str | None,
    feed: str | None = None,
    ttl_seconds: float = 86_400.0,
) -> dict[str, list[MarketBar]]:
    request = MarketDataRequest(
        symbols=symbols,
        asset_class=asset_class,
        timeframe=timeframe,
        start=start,
        end=end,
        feed=feed,
    )
    response = data_layer.historical_bars(request, ttl_seconds=ttl_seconds)
    return _normalize_records(symbols, response.records)
