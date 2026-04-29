from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import fmean
from zoneinfo import ZoneInfo

from trading_system.data.models import MarketBar


@dataclass(frozen=True)
class PatternObservation:
    strategy: str
    symbol: str
    trigger_time: str
    trigger_type: str
    entry_timing: str
    forward_return_pct: float
    max_adverse_move_pct: float
    source: str
    notes: tuple[str, ...] = ()


def percent_change(previous: float, current: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous * 100.0


def moving_average(values: list[float], end_index: int, window: int) -> float:
    if end_index + 1 < window:
        return 0.0
    subset = values[end_index + 1 - window : end_index + 1]
    return fmean(subset)


def max_adverse_long(bars: list[MarketBar], entry_index: int, exit_index: int) -> float:
    entry = bars[entry_index].close
    if entry <= 0:
        return 0.0
    lows = [bar.low for bar in bars[entry_index : exit_index + 1] if bar.low > 0]
    return percent_change(entry, min(lows)) if lows else 0.0


def _date_key(timestamp: str) -> str:
    return timestamp[:10]


def _parse_timestamp(timestamp: str) -> datetime:
    normalized = timestamp.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def _is_regular_equity_session(timestamp: str) -> bool:
    eastern = _parse_timestamp(timestamp).astimezone(ZoneInfo("America/New_York"))
    minutes = eastern.hour * 60 + eastern.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def _eastern_time_label(timestamp: str) -> str:
    return _parse_timestamp(timestamp).astimezone(ZoneInfo("America/New_York")).strftime("%H:%M ET")


def group_intraday_by_symbol_day(
    bars_by_symbol: dict[str, list[MarketBar]],
) -> dict[str, dict[str, list[MarketBar]]]:
    grouped: dict[str, dict[str, list[MarketBar]]] = {}
    for symbol, bars in bars_by_symbol.items():
        by_day: dict[str, list[MarketBar]] = defaultdict(list)
        for bar in sorted(bars, key=lambda item: item.timestamp):
            if not _is_regular_equity_session(bar.timestamp):
                continue
            by_day[_date_key(bar.timestamp)].append(bar)
        grouped[symbol] = dict(by_day)
    return grouped


def detect_etf_time_series_momentum(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    horizon_days: int = 20,
) -> list[PatternObservation]:
    observations: list[PatternObservation] = []
    for symbol, bars in bars_by_symbol.items():
        closes = [bar.close for bar in bars]
        previous_signal = False
        for index in range(200, len(bars) - horizon_days):
            sma_50 = moving_average(closes, index, 50)
            sma_200 = moving_average(closes, index, 200)
            ret_20 = percent_change(closes[index - 20], closes[index])
            ret_60 = percent_change(closes[index - 60], closes[index])
            signal = closes[index] > sma_50 > sma_200 and ret_20 > 0 and ret_60 > 0
            if signal and not previous_signal:
                observations.append(
                    PatternObservation(
                        strategy="etf_time_series_momentum_v1",
                        symbol=symbol,
                        trigger_time=bars[index].timestamp,
                        trigger_type="fresh_50_200_momentum_alignment",
                        entry_timing="next daily bar after close confirmation",
                        forward_return_pct=percent_change(closes[index], closes[index + horizon_days]),
                        max_adverse_move_pct=max_adverse_long(bars, index, index + horizon_days),
                        source="alpaca_daily",
                        notes=(f"ret20={ret_20:.2f}%", f"ret60={ret_60:.2f}%"),
                    )
                )
            previous_signal = signal
    return observations


def detect_cross_sectional_rotation(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    lookback_days: int = 60,
    hold_days: int = 20,
    top_n: int = 2,
    step_days: int = 5,
) -> list[PatternObservation]:
    usable = {symbol: bars for symbol, bars in bars_by_symbol.items() if len(bars) > lookback_days + hold_days}
    if len(usable) < top_n:
        return []
    max_len = min(len(bars) for bars in usable.values())
    observations: list[PatternObservation] = []
    for index in range(lookback_days, max_len - hold_days, step_days):
        ranked: list[tuple[float, str, list[MarketBar]]] = []
        for symbol, bars in usable.items():
            score = percent_change(bars[index - lookback_days].close, bars[index].close)
            ranked.append((score, symbol, bars))
        ranked.sort(reverse=True)
        for score, symbol, bars in ranked[:top_n]:
            observations.append(
                PatternObservation(
                    strategy="cross_sectional_momentum_rotation_v1",
                    symbol=symbol,
                    trigger_time=bars[index].timestamp,
                    trigger_type="top_cross_sectional_60d_momentum",
                    entry_timing="weekly rank review, next daily bar",
                    forward_return_pct=percent_change(bars[index].close, bars[index + hold_days].close),
                    max_adverse_move_pct=max_adverse_long(bars, index, index + hold_days),
                    source="alpaca_daily",
                    notes=(f"rank_score={score:.2f}%",),
                )
            )
    return observations


def detect_opening_range_breakouts(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    opening_minutes: int = 15,
) -> list[PatternObservation]:
    observations: list[PatternObservation] = []
    for symbol, by_day in group_intraday_by_symbol_day(bars_by_symbol).items():
        for bars in by_day.values():
            if len(bars) <= opening_minutes + 10:
                continue
            opening = bars[:opening_minutes]
            high = max(bar.high for bar in opening)
            average_opening_volume = fmean([bar.volume for bar in opening]) if opening else 0.0
            for index in range(opening_minutes, len(bars)):
                if bars[index].close <= high:
                    continue
                volume_note = "volume_unconfirmed"
                if average_opening_volume > 0 and bars[index].volume >= average_opening_volume:
                    volume_note = "volume_confirmed"
                observations.append(
                    PatternObservation(
                        strategy="opening_range_breakout_v1",
                        symbol=symbol,
                        trigger_time=bars[index].timestamp,
                        trigger_type=f"{opening_minutes}m_opening_range_high_break",
                        entry_timing="first close above opening-range high after blackout window",
                        forward_return_pct=percent_change(bars[index].close, bars[-1].close),
                        max_adverse_move_pct=max_adverse_long(bars, index, len(bars) - 1),
                        source="alpaca_intraday",
                        notes=(volume_note, f"entry_time={_eastern_time_label(bars[index].timestamp)}"),
                    )
                )
                break
    return observations


def detect_vwap_mean_reversion(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    stretch_pct: float = 0.35,
    min_minutes_after_open: int = 30,
    horizon_minutes: int = 30,
) -> list[PatternObservation]:
    observations: list[PatternObservation] = []
    for symbol, by_day in group_intraday_by_symbol_day(bars_by_symbol).items():
        for bars in by_day.values():
            cumulative_price_volume = 0.0
            cumulative_volume = 0.0
            for index, bar in enumerate(bars):
                cumulative_price_volume += bar.close * bar.volume
                cumulative_volume += bar.volume
                if index < min_minutes_after_open or cumulative_volume <= 0:
                    continue
                vwap = cumulative_price_volume / cumulative_volume
                if vwap <= 0:
                    continue
                deviation = percent_change(vwap, bar.close)
                if deviation > -abs(stretch_pct):
                    continue
                exit_index = min(len(bars) - 1, index + horizon_minutes)
                observations.append(
                    PatternObservation(
                        strategy="vwap_mean_reversion_v1",
                        symbol=symbol,
                        trigger_time=bar.timestamp,
                        trigger_type="below_vwap_stretch",
                        entry_timing=f"after {min_minutes_after_open} minutes, exit check at {horizon_minutes} minutes",
                        forward_return_pct=percent_change(bar.close, bars[exit_index].close),
                        max_adverse_move_pct=max_adverse_long(bars, index, exit_index),
                        source="alpaca_intraday",
                        notes=(f"vwap_deviation={deviation:.2f}%",),
                    )
                )
                break
    return observations


def detect_crypto_breakouts(
    bars_by_symbol: dict[str, list[MarketBar]],
    *,
    breakout_days: int = 20,
    horizon_days: int = 10,
) -> list[PatternObservation]:
    observations: list[PatternObservation] = []
    for symbol, bars in bars_by_symbol.items():
        for index in range(breakout_days, len(bars) - horizon_days):
            prior_high = max(bar.high for bar in bars[index - breakout_days : index])
            if bars[index].close <= prior_high:
                continue
            weekday = _parse_timestamp(bars[index].timestamp).weekday()
            observations.append(
                PatternObservation(
                    strategy="crypto_trend_breakout_v1",
                    symbol=symbol,
                    trigger_time=bars[index].timestamp,
                    trigger_type="20d_high_breakout",
                    entry_timing="daily close confirmation; 24/7 monitoring required",
                    forward_return_pct=percent_change(bars[index].close, bars[index + horizon_days].close),
                    max_adverse_move_pct=max_adverse_long(bars, index, index + horizon_days),
                    source="alpaca_crypto_daily",
                    notes=("weekend" if weekday >= 5 else "weekday",),
                )
            )
    return observations


def summarize_observations(observations: list[PatternObservation]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[PatternObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.strategy].append(observation)
    summary: dict[str, dict[str, object]] = {}
    for strategy, items in grouped.items():
        returns = [item.forward_return_pct for item in items]
        adverse = [item.max_adverse_move_pct for item in items]
        by_trigger: dict[str, int] = defaultdict(int)
        by_symbol: dict[str, int] = defaultdict(int)
        for item in items:
            by_trigger[item.trigger_type] += 1
            by_symbol[item.symbol] += 1
        summary[strategy] = {
            "observation_count": len(items),
            "average_forward_return_pct": fmean(returns) if returns else 0.0,
            "median_forward_return_pct": sorted(returns)[len(returns) // 2] if returns else 0.0,
            "positive_rate": sum(1 for value in returns if value > 0) / len(returns) if returns else 0.0,
            "average_max_adverse_move_pct": fmean(adverse) if adverse else 0.0,
            "by_trigger": dict(sorted(by_trigger.items())),
            "by_symbol": dict(sorted(by_symbol.items())),
        }
    return summary


def observations_to_dict(observations: list[PatternObservation]) -> list[dict[str, object]]:
    return [asdict(item) for item in observations]
