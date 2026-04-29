from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class WalkForwardWindow(Generic[T]):
    train: tuple[T, ...]
    test: tuple[T, ...]
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int


def build_walk_forward_windows(
    observations: Sequence[T],
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
) -> list[WalkForwardWindow[T]]:
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step_size is None else step_size
    if step <= 0:
        raise ValueError("step_size must be positive")
    windows: list[WalkForwardWindow[T]] = []
    start = 0
    total = len(observations)
    while start + train_size + test_size <= total:
        train_start = start
        train_end = start + train_size
        test_start = train_end
        test_end = test_start + test_size
        windows.append(
            WalkForwardWindow(
                train=tuple(observations[train_start:train_end]),
                test=tuple(observations[test_start:test_end]),
                train_start_index=train_start,
                train_end_index=train_end - 1,
                test_start_index=test_start,
                test_end_index=test_end - 1,
            )
        )
        start += step
    if not windows:
        raise ValueError("not enough observations for one walk-forward window")
    return windows

