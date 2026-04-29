from __future__ import annotations

from datetime import date, timedelta

from trading_system.data.models import MarketBar


def bars_from_prices(symbol: str, prices: list[float], *, start: date = date(2025, 1, 1), volume: float = 1_000_000.0) -> list[MarketBar]:
    bars: list[MarketBar] = []
    for index, close in enumerate(prices):
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=(start + timedelta(days=index)).isoformat(),
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=volume + index * 100.0,
            )
        )
    return bars


def trend_prices(*, drift: float, length: int = 260, base: float = 100.0) -> list[float]:
    return [base + drift * index for index in range(length)]


def default_quotes(symbols: tuple[str, ...] | list[str]) -> dict[str, dict[str, float]]:
    return {symbol: {"bid": 100.00, "ask": 100.05} for symbol in symbols}
