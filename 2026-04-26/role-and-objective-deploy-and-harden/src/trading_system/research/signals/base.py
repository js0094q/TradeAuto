from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SignalMetadata:
    name: str
    category: str
    description: str
    required_inputs: tuple[str, ...]
    output_range: tuple[float, float]
    interpretation: str
    known_failure_modes: tuple[str, ...]
    roles: tuple[str, ...]
    asset_classes: tuple[str, ...]


@dataclass(frozen=True)
class SignalResult:
    name: str
    value: float
    interpretation: str
    metadata: SignalMetadata
    suppression_reason: str | None = None
    inputs_used: Mapping[str, float | int | str] = field(default_factory=dict)

    @property
    def suppressed(self) -> bool:
        return self.suppression_reason is not None


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_divide(numerator: float, denominator: float, *, default: float = 0.0) -> float:
    if denominator == 0 or math.isnan(denominator):
        return default
    return numerator / denominator


def require_length(values: Sequence[float], minimum: int, name: str) -> None:
    if len(values) < minimum:
        raise ValueError(f"{name} requires at least {minimum} observations")


def mean(values: Sequence[float]) -> float:
    require_length(values, 1, "mean")
    return statistics.fmean(values)


def pstdev(values: Sequence[float]) -> float:
    require_length(values, 2, "standard deviation")
    return statistics.pstdev(values)


def pct_change(old: float, new: float) -> float:
    return safe_divide(new - old, old)


def z_score(values: Sequence[float], *, window: int) -> float:
    require_length(values, window, "z_score")
    sample = values[-window:]
    std = pstdev(sample)
    return safe_divide(sample[-1] - mean(sample), std)


def no_lookahead_window(values: Sequence[float], *, end_exclusive: int, window: int) -> tuple[float, ...]:
    if end_exclusive < window:
        raise ValueError("window would require unavailable future or pre-sample data")
    return tuple(values[end_exclusive - window : end_exclusive])

