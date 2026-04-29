from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from trading_system.data.cache import ResearchCache, cache_key
from trading_system.data.rate_limits import RateLimitGuard, retry_with_backoff


class MarketDataProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketDataRequest:
    symbols: tuple[str, ...]
    asset_class: str
    timeframe: str
    start: str
    end: str | None = None
    feed: str | None = None


@dataclass(frozen=True)
class MarketDataResponse:
    request: MarketDataRequest
    records: Mapping[str, object]
    source: str
    fetched_at: float
    cached: bool = False


class ReadOnlyAlpacaMarketData:
    """Research-only market-data adapter; never exposes account or order methods."""

    def __init__(
        self,
        *,
        fetcher: Callable[[MarketDataRequest], Mapping[str, object]] | None = None,
        rate_limit: RateLimitGuard | None = None,
        cache: ResearchCache | None = None,
        source: str = "alpaca_market_data",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.fetcher = fetcher
        self.rate_limit = rate_limit or RateLimitGuard(max_calls=10_000, period_seconds=60.0)
        self.cache = cache or ResearchCache(default_ttl_seconds=300.0, clock=clock)
        self.source = source
        self.clock = clock

    def historical_bars(self, request: MarketDataRequest, *, ttl_seconds: float = 300.0) -> MarketDataResponse:
        key = cache_key("historical_bars", request.asset_class, request.timeframe, ",".join(request.symbols), request.start, request.end or "", request.feed or "")
        cached = self.cache.get(key)
        if cached is not None:
            return MarketDataResponse(request=request, records=cached, source=self.source, fetched_at=self.clock(), cached=True)
        if self.fetcher is None:
            raise MarketDataProviderError("read-only market-data fetcher is not configured")
        self.rate_limit.record(cost=max(1, len(request.symbols)))
        records = retry_with_backoff(lambda: self.fetcher(request))
        self.cache.set(key, records, ttl_seconds=ttl_seconds)
        return MarketDataResponse(request=request, records=records, source=self.source, fetched_at=self.clock(), cached=False)

