from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


class ChronologyError(ValueError):
    pass


@dataclass(frozen=True)
class TrainValidationTestSplit(Generic[T]):
    train: tuple[T, ...]
    validation: tuple[T, ...]
    test: tuple[T, ...]


def train_validation_test_split(
    observations: Sequence[T],
    *,
    train_ratio: float = 0.60,
    validation_ratio: float = 0.20,
) -> TrainValidationTestSplit[T]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must leave a test set")
    count = len(observations)
    if count < 3:
        raise ValueError("at least three observations are required")
    train_end = max(1, int(count * train_ratio))
    validation_end = max(train_end + 1, int(count * (train_ratio + validation_ratio)))
    if validation_end >= count:
        validation_end = count - 1
    return TrainValidationTestSplit(
        train=tuple(observations[:train_end]),
        validation=tuple(observations[train_end:validation_end]),
        test=tuple(observations[validation_end:]),
    )


def assert_chronological_no_lookahead(
    train: Sequence[T],
    validation: Sequence[T],
    test: Sequence[T],
    *,
    key: Callable[[T], object],
) -> None:
    if not train or not validation or not test:
        raise ChronologyError("train, validation, and test sets must be non-empty")
    if key(train[-1]) >= key(validation[0]):
        raise ChronologyError("training data overlaps or follows validation data")
    if key(validation[-1]) >= key(test[0]):
        raise ChronologyError("validation data overlaps or follows test data")
