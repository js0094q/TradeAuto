from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any


def finite_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _window(values: Sequence[object], size: int) -> tuple[float, ...] | None:
    if size <= 0 or len(values) < size:
        return None
    output: list[float] = []
    for value in values[-size:]:
        number = finite_float(value)
        if number is None:
            return None
        output.append(number)
    return tuple(output)


def sma(values: Sequence[object], window: int) -> float | None:
    sample = _window(values, window)
    if sample is None:
        return None
    return statistics.fmean(sample)


def ema(values: Sequence[object], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    numbers: list[float] = []
    for value in values:
        number = finite_float(value)
        if number is None:
            return None
        numbers.append(number)
    seed = statistics.fmean(numbers[:window])
    alpha = 2.0 / (window + 1.0)
    current = seed
    for value in numbers[window:]:
        current = value * alpha + current * (1.0 - alpha)
    return current


def rolling_return(values: Sequence[object], lookback: int) -> float | None:
    if lookback <= 0 or len(values) <= lookback:
        return None
    current = finite_float(values[-1])
    previous = finite_float(values[-lookback - 1])
    if current is None or previous in (None, 0.0):
        return None
    return (current - previous) / previous


def realized_volatility(values: Sequence[object], window: int) -> float | None:
    if window <= 1 or len(values) <= window:
        return None
    sample = _window(values, window + 1)
    if sample is None:
        return None
    returns: list[float] = []
    for index in range(1, len(sample)):
        previous = sample[index - 1]
        if previous == 0.0:
            return None
        returns.append((sample[index] - previous) / previous)
    return statistics.pstdev(returns) if len(returns) > 1 else 0.0


def rsi(values: Sequence[object], window: int = 14) -> float | None:
    if window <= 0 or len(values) <= window:
        return None
    sample = _window(values, window + 1)
    if sample is None:
        return None
    changes = [sample[index] - sample[index - 1] for index in range(1, len(sample))]
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]
    average_gain = statistics.fmean(gains)
    average_loss = statistics.fmean(losses)
    if average_loss == 0.0:
        return 100.0 if average_gain > 0.0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def rolling_z_score(values: Sequence[object], window: int) -> float | None:
    sample = _window(values, window)
    if sample is None:
        return None
    deviation = statistics.pstdev(sample)
    if deviation == 0.0:
        return 0.0
    return (sample[-1] - statistics.fmean(sample)) / deviation


def mean_reversion_z_score(values: Sequence[object], *, mean_window: int = 5, z_window: int = 20) -> float | None:
    current = finite_float(values[-1]) if values else None
    mean_value = sma(values, mean_window)
    sample = _window(values, z_window)
    if current is None or mean_value is None or sample is None:
        return None
    deviation = statistics.pstdev(sample)
    if deviation == 0.0:
        return 0.0
    return (mean_value - current) / deviation


def _bar_value(bar: object, name: str) -> float | None:
    if isinstance(bar, Mapping):
        return finite_float(bar.get(name))
    return finite_float(getattr(bar, name, None))


def close_values(bars: Sequence[object]) -> list[float]:
    values: list[float] = []
    for bar in bars:
        close = _bar_value(bar, "close")
        if close is None:
            return []
        values.append(close)
    return values


def true_range(current_bar: object, previous_close: float) -> float | None:
    high = _bar_value(current_bar, "high")
    low = _bar_value(current_bar, "low")
    if high is None or low is None:
        return None
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def atr(bars: Sequence[object], window: int = 14) -> float | None:
    if window <= 0 or len(bars) <= window:
        return None
    ranges: list[float] = []
    for index in range(len(bars) - window, len(bars)):
        previous_close = _bar_value(bars[index - 1], "close")
        if previous_close is None:
            return None
        value = true_range(bars[index], previous_close)
        if value is None:
            return None
        ranges.append(value)
    return statistics.fmean(ranges) if ranges else None


def relative_volume(bars: Sequence[object], window: int = 20) -> float | None:
    if window <= 0 or len(bars) <= window:
        return None
    baseline_values: list[float] = []
    for bar in bars[-window - 1 : -1]:
        volume = _bar_value(bar, "volume")
        if volume is None:
            return None
        baseline_values.append(volume)
    current_volume = _bar_value(bars[-1], "volume")
    baseline = statistics.fmean(baseline_values) if baseline_values else 0.0
    if current_volume is None or baseline <= 0.0:
        return None
    return current_volume / baseline


def spread_bps(quote: object | None) -> float | None:
    if quote is None:
        return None
    if isinstance(quote, Mapping):
        explicit_bps = finite_float(quote.get("spread_bps"))
        if explicit_bps is not None:
            return explicit_bps
        spread_pct = finite_float(quote.get("spread_pct"))
        if spread_pct is not None:
            return spread_pct * 100.0
        bid = finite_float(quote.get("bid"))
        ask = finite_float(quote.get("ask"))
    else:
        spread_pct = finite_float(getattr(quote, "spread_pct", None))
        if spread_pct is not None:
            return spread_pct * 100.0
        bid = finite_float(getattr(quote, "bid", None))
        ask = finite_float(getattr(quote, "ask", None))
    if bid is None or ask is None or bid <= 0.0 or ask <= 0.0 or ask < bid:
        return None
    midpoint = (bid + ask) / 2.0
    return None if midpoint <= 0.0 else (ask - bid) / midpoint * 10_000.0


def parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        seconds = number / 1000.0 if number > 10_000_000_000 else float(number)
        return datetime.fromtimestamp(seconds, tz=UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def latest_bar_timestamp(bars: Sequence[Any]) -> datetime | None:
    if not bars:
        return None
    if isinstance(bars[-1], Mapping):
        raw = bars[-1].get("timestamp")
    else:
        raw = getattr(bars[-1], "timestamp", None)
    return parse_timestamp(raw)


def bars_are_stale(bars: Sequence[Any], *, as_of: datetime, max_age_days: int = 5) -> bool:
    latest = latest_bar_timestamp(bars)
    if latest is None:
        return True
    return (as_of.astimezone(UTC) - latest.astimezone(UTC)).days > max_age_days
