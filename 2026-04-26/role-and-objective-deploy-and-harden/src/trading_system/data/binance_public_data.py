from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from trading_system.data.models import MarketBar
from trading_system.data.provider import DataCache, MarketDataProviderError


def _to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class _StdlibSession:
    def get(self, url: str, *, params: dict[str, object], timeout: int) -> Any:
        query = urlencode(params)
        with urlopen(f"{url}?{query}", timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            payload = json.loads(response.read().decode("utf-8"))

        class _Response:
            def __init__(self, data: object, code: int) -> None:
                self._data = data
                self.status_code = code

            def json(self) -> object:
                return self._data

        return _Response(payload, status_code)


@dataclass(frozen=True)
class BinancePublicDataProvider:
    """Research-only read adapter for Binance public spot klines."""

    session: Any
    cache: DataCache
    timeout_seconds: int = 30
    base_url: str = "https://data-api.binance.vision/api/v3/klines"
    default_limit: int = 1000

    def __init__(
        self,
        *,
        session: object | None = None,
        cache: DataCache | None = None,
        timeout_seconds: int = 30,
        base_url: str = "https://data-api.binance.vision/api/v3/klines",
        default_limit: int = 1000,
    ) -> None:
        object.__setattr__(self, "session", session or _StdlibSession())
        object.__setattr__(self, "cache", cache or DataCache("data/research_market_cache", ttl_seconds=3_600))
        object.__setattr__(self, "timeout_seconds", timeout_seconds)
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "default_limit", min(1000, max(1, default_limit)))

    def _cache_key(
        self,
        *,
        symbol: str,
        interval: str,
        start_ms: int | None,
        end_ms: int | None,
        limit: int,
    ) -> str:
        return "|".join(
            (
                "binance_spot_klines",
                f"symbol={symbol.upper()}",
                f"interval={interval}",
                f"start_ms={start_ms or ''}",
                f"end_ms={end_ms or ''}",
                f"limit={limit}",
            )
        )

    def _load_rows(
        self,
        *,
        symbol: str,
        interval: str,
        start_ms: int | None,
        end_ms: int | None,
        limit: int,
    ) -> list[list[Any]]:
        cache_key = self._cache_key(symbol=symbol, interval=interval, start_ms=start_ms, end_ms=end_ms, limit=limit)
        cached = self.cache.get(cache_key)
        if cached is not None:
            rows = cached.payload.get("rows", [])
            if isinstance(rows, list):
                return rows

        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        response = self.session.get(self.base_url, params=params, timeout=self.timeout_seconds)
        if response.status_code != 200:
            raise MarketDataProviderError(
                f"binance public request failed for {symbol}: HTTP {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, list):
            raise MarketDataProviderError(f"unexpected binance payload for {symbol}")
        self.cache.set(
            cache_key,
            {"rows": payload},
            source="binance_spot_klines",
            fetched_at=time.time(),
            ttl_seconds=self.cache.ttl_seconds,
        )
        return payload

    def fetch_spot_bars(
        self,
        symbol: str,
        *,
        interval: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]:
        page_limit = self.default_limit if limit is None else min(1000, max(1, limit))
        cursor = start_ms
        bars: list[MarketBar] = []
        seen_timestamps: set[int] = set()

        while True:
            rows = self._load_rows(
                symbol=symbol,
                interval=interval,
                start_ms=cursor,
                end_ms=end_ms,
                limit=page_limit,
            )
            if not rows:
                break

            for row in rows:
                if not isinstance(row, list) or len(row) < 6:
                    continue
                open_time = int(row[0])
                if open_time in seen_timestamps:
                    continue
                seen_timestamps.add(open_time)
                bars.append(
                    MarketBar(
                        symbol=symbol.upper(),
                        timestamp=str(open_time),
                        open=_to_float(row[1]),
                        high=_to_float(row[2]),
                        low=_to_float(row[3]),
                        close=_to_float(row[4]),
                        volume=_to_float(row[5]),
                        vwap=None,
                    )
                )

            last_open_time = int(rows[-1][0])
            if len(rows) < page_limit:
                break
            next_cursor = last_open_time + 1
            if cursor is not None and next_cursor <= cursor:
                break
            if end_ms is not None and next_cursor > end_ms:
                break
            cursor = next_cursor

        return sorted(bars, key=lambda item: int(item.timestamp))
