from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None


@dataclass(frozen=True)
class Quote:
    symbol: str
    timestamp: str
    bid: float
    ask: float
    bid_size: int | None = None
    ask_size: int | None = None

    @property
    def spread(self) -> float:
        if self.bid <= 0 or self.ask <= 0:
            return 0.0
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        if self.bid <= 0:
            return 0.0
        return self.spread / self.bid * 100.0


@dataclass(frozen=True)
class Trade:
    symbol: str
    timestamp: str
    price: float
    size: int | float
    exchange: str | None = None


@dataclass(frozen=True)
class Snapshot:
    symbol: str
    timestamp: str
    price: float
    bid: float
    ask: float
    volume: float | None = None


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    strike: float
    expiration: str
    right: str
    bid: float
    ask: float
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None


@dataclass(frozen=True)
class OptionChain:
    underlying: str
    contracts: tuple[OptionContract, ...]
    expiration: str | None = None
