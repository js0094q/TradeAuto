from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trading_system.data.models import MarketBar, OptionChain, OptionContract, Quote, Snapshot, Trade


class MarketDataProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class CachedRecord:
    payload: dict[str, Any]
    fetched_at: float
    source: str
    expires_at: float


class DataCache:
    """File-based JSON cache for provider payloads."""

    def __init__(self, root: str | Path = "data/market_cache", *, ttl_seconds: float = 300.0) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.root = Path(root)
        self.ttl_seconds = float(ttl_seconds)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        hashed = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{hashed}.json"

    def get(self, key: str, *, now: float | None = None) -> CachedRecord | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        payload = raw.get("payload", {})
        if not isinstance(payload, dict):
            return None
        fetched_at = float(raw.get("fetched_at", 0.0))
        source = str(raw.get("source", "unknown"))
        expires_at = float(raw.get("expires_at", fetched_at))
        now_value = time.time() if now is None else now
        if now_value > expires_at:
            return None
        return CachedRecord(payload=payload, fetched_at=fetched_at, source=source, expires_at=expires_at)

    def set(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        source: str,
        fetched_at: float,
        ttl_seconds: float | None = None,
    ) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        path = self._path_for(key)
        path.write_text(
            json.dumps(
                {
                    "payload": payload,
                    "fetched_at": fetched_at,
                    "source": source,
                    "expires_at": fetched_at + ttl,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        for file in self.root.glob("*.json"):
            file.unlink(missing_ok=True)


class MarketDataProvider(ABC):
    """Provider interface for read-only market data."""

    @abstractmethod
    def fetch_bars(
        self,
        symbols: tuple[str, ...],
        timeframe: str,
        start: str,
        end: str | None = None,
    ) -> dict[str, list[MarketBar]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, Quote]:
        raise NotImplementedError

    @abstractmethod
    def fetch_latest_trade(self, symbols: tuple[str, ...]) -> dict[str, Trade]:
        raise NotImplementedError

    @abstractmethod
    def fetch_snapshot(self, symbols: tuple[str, ...]) -> dict[str, Snapshot]:
        raise NotImplementedError

    @abstractmethod
    def fetch_crypto_bars(
        self,
        symbols: tuple[str, ...],
        timeframe: str,
        start: str,
        end: str | None = None,
    ) -> dict[str, list[MarketBar]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_option_chain(self, underlying: str, expiration: str | None = None) -> OptionChain:
        raise NotImplementedError

    @abstractmethod
    def fetch_option_quotes(self, contracts: tuple[str, ...]) -> dict[str, Quote]:
        raise NotImplementedError

    @abstractmethod
    def fetch_option_snapshot(self, contracts: tuple[str, ...]) -> dict[str, Snapshot]:
        raise NotImplementedError


def _bars_payload(values: dict[str, list[MarketBar]]) -> dict[str, Any]:
    return {
        symbol: [
            {
                "symbol": bar.symbol,
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "vwap": bar.vwap,
            }
            for bar in bars
        ]
        for symbol, bars in values.items()
    }


def _bars_from_payload(payload: dict[str, Any]) -> dict[str, list[MarketBar]]:
    output: dict[str, list[MarketBar]] = {}
    for symbol, raw_bars in payload.items():
        output[symbol] = [
            MarketBar(
                symbol=str(symbol),
                timestamp=str(item["timestamp"]),
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=float(item["volume"]),
                vwap=(float(item["vwap"]) if item.get("vwap") is not None else None),
            )
            for item in (raw_bars if isinstance(raw_bars, list) else [])
        ]
    return output


def _quotes_payload(values: dict[str, Quote]) -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "symbol": quote.symbol,
            "timestamp": quote.timestamp,
            "bid": quote.bid,
            "ask": quote.ask,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
        }
        for symbol, quote in values.items()
    }


def _quotes_from_payload(payload: dict[str, Any]) -> dict[str, Quote]:
    return {
        symbol: Quote(
            symbol=symbol,
            timestamp=str(item["timestamp"]),
            bid=float(item["bid"]),
            ask=float(item["ask"]),
            bid_size=(int(item["bid_size"]) if item.get("bid_size") is not None else None),
            ask_size=(int(item["ask_size"]) if item.get("ask_size") is not None else None),
        )
        for symbol, item in payload.items()
    }


def _trades_payload(values: dict[str, Trade]) -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "symbol": trade.symbol,
            "timestamp": trade.timestamp,
            "price": trade.price,
            "size": trade.size,
            "exchange": trade.exchange,
        }
        for symbol, trade in values.items()
    }


def _trades_from_payload(payload: dict[str, Any]) -> dict[str, Trade]:
    return {
        symbol: Trade(
            symbol=symbol,
            timestamp=str(item["timestamp"]),
            price=float(item["price"]),
            size=item["size"],
            exchange=(str(item["exchange"]) if item.get("exchange") is not None else None),
        )
        for symbol, item in payload.items()
    }


def _snapshot_payload(values: dict[str, Snapshot]) -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "symbol": snapshot.symbol,
            "timestamp": snapshot.timestamp,
            "price": snapshot.price,
            "bid": snapshot.bid,
            "ask": snapshot.ask,
            "volume": snapshot.volume,
        }
        for symbol, snapshot in values.items()
    }


def _snapshot_from_payload(payload: dict[str, Any]) -> dict[str, Snapshot]:
    return {
        symbol: Snapshot(
            symbol=symbol,
            timestamp=str(item["timestamp"]),
            price=float(item["price"]),
            bid=float(item["bid"]),
            ask=float(item["ask"]),
            volume=(float(item["volume"]) if item.get("volume") is not None else None),
        )
        for symbol, item in payload.items()
    }


def _option_chain_payload(chain: OptionChain) -> dict[str, Any]:
    return {
        "underlying": chain.underlying,
        "expiration": chain.expiration,
        "contracts": [
            {
                "symbol": contract.symbol,
                "strike": contract.strike,
                "expiration": contract.expiration,
                "right": contract.right,
                "bid": contract.bid,
                "ask": contract.ask,
                "volume": contract.volume,
                "open_interest": contract.open_interest,
                "implied_volatility": contract.implied_volatility,
            }
            for contract in chain.contracts
        ],
    }


def _option_chain_from_payload(payload: dict[str, Any]) -> OptionChain:
    return OptionChain(
        underlying=str(payload.get("underlying", "")),
        expiration=(str(payload["expiration"]) if payload.get("expiration") else None),
        contracts=tuple(
            OptionContract(
                symbol=str(item["symbol"]),
                strike=float(item["strike"]),
                expiration=str(item["expiration"]),
                right=str(item["right"]),
                bid=float(item["bid"]),
                ask=float(item["ask"]),
                volume=(int(item["volume"]) if item.get("volume") is not None else None),
                open_interest=(int(item["open_interest"]) if item.get("open_interest") is not None else None),
                implied_volatility=(float(item["implied_volatility"]) if item.get("implied_volatility") is not None else None),
            )
            for item in payload.get("contracts", [])
            if isinstance(payload.get("contracts"), list)
        ),
    )


class CachedMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: DataCache,
        *,
        now_fn: Callable[[], float] = time.time,
        default_ttl_seconds: float | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.now_fn = now_fn
        self.default_ttl_seconds = default_ttl_seconds

    def _cache_key(self, method: str, **parts: object) -> str:
        ordered_parts = [method] + [f"{key}={value}" for key, value in sorted(parts.items())]
        return "|".join(ordered_parts).lower()

    def _with_cache(
        self,
        method: str,
        serializer: Callable[[Any], dict[str, Any]],
        deserializer: Callable[[dict[str, Any]], Any],
        loader: Callable[[], dict[str, Any]],
        **parts: object,
    ) -> Any:
        key = self._cache_key(method, **parts)
        now = self.now_fn()
        cached = self.cache.get(key, now=now)
        if cached is not None:
            return deserializer(cached.payload)
        loaded = loader()
        self.cache.set(key, serializer(loaded), source=method, fetched_at=now, ttl_seconds=self.default_ttl_seconds)
        return loaded

    def fetch_bars(self, symbols: tuple[str, ...], timeframe: str, start: str, end: str | None = None) -> dict[str, list[MarketBar]]:
        def loader() -> dict[str, list[MarketBar]]:
            return self.provider.fetch_bars(symbols=tuple(symbols), timeframe=timeframe, start=start, end=end)

        return self._with_cache(
            "fetch_bars",
            _bars_payload,
            _bars_from_payload,
            loader,
            symbols=tuple(sorted(symbols)),
            timeframe=timeframe,
            start=start,
            end=end or "",
        )

    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, Quote]:
        def loader() -> dict[str, Quote]:
            return self.provider.fetch_latest_quote(symbols=tuple(symbols))

        return self._with_cache(
            "fetch_latest_quote",
            _quotes_payload,
            _quotes_from_payload,
            loader,
            symbols=tuple(sorted(symbols)),
        )

    def fetch_latest_trade(self, symbols: tuple[str, ...]) -> dict[str, Trade]:
        def loader() -> dict[str, Trade]:
            return self.provider.fetch_latest_trade(symbols=tuple(symbols))

        return self._with_cache(
            "fetch_latest_trade",
            _trades_payload,
            _trades_from_payload,
            loader,
            symbols=tuple(sorted(symbols)),
        )

    def fetch_snapshot(self, symbols: tuple[str, ...]) -> dict[str, Snapshot]:
        def loader() -> dict[str, Snapshot]:
            return self.provider.fetch_snapshot(symbols=tuple(symbols))

        return self._with_cache(
            "fetch_snapshot",
            _snapshot_payload,
            _snapshot_from_payload,
            loader,
            symbols=tuple(sorted(symbols)),
        )

    def fetch_crypto_bars(
        self,
        symbols: tuple[str, ...],
        timeframe: str,
        start: str,
        end: str | None = None,
    ) -> dict[str, list[MarketBar]]:
        def loader() -> dict[str, list[MarketBar]]:
            return self.provider.fetch_crypto_bars(symbols=tuple(symbols), timeframe=timeframe, start=start, end=end)

        return self._with_cache(
            "fetch_crypto_bars",
            _bars_payload,
            _bars_from_payload,
            loader,
            symbols=tuple(sorted(symbols)),
            timeframe=timeframe,
            start=start,
            end=end or "",
        )

    def fetch_option_chain(self, underlying: str, expiration: str | None = None) -> OptionChain:
        def loader() -> OptionChain:
            return self.provider.fetch_option_chain(underlying=underlying, expiration=expiration)

        return self._with_cache(
            "fetch_option_chain",
            _option_chain_payload,
            _option_chain_from_payload,
            loader,
            underlying=underlying,
            expiration=expiration or "",
        )

    def fetch_option_quotes(self, contracts: tuple[str, ...]) -> dict[str, Quote]:
        def loader() -> dict[str, Quote]:
            return self.provider.fetch_option_quotes(contracts=tuple(contracts))

        return self._with_cache(
            "fetch_option_quotes",
            _quotes_payload,
            _quotes_from_payload,
            loader,
            contracts=tuple(sorted(contracts)),
        )

    def fetch_option_snapshot(self, contracts: tuple[str, ...]) -> dict[str, Snapshot]:
        def loader() -> dict[str, Snapshot]:
            return self.provider.fetch_option_snapshot(contracts=tuple(contracts))

        return self._with_cache(
            "fetch_option_snapshot",
            _snapshot_payload,
            _snapshot_from_payload,
            loader,
            contracts=tuple(sorted(contracts)),
        )

