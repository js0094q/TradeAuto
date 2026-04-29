from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import TypeVar


T = TypeVar("T")


class RateLimitExceeded(RuntimeError):
    def __init__(self, wait_seconds: float) -> None:
        super().__init__(f"rate limit exceeded; retry after {wait_seconds:.3f}s")
        self.wait_seconds = wait_seconds


@dataclass
class RateLimitGuard:
    max_calls: int
    period_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic
    _calls: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if self.period_seconds <= 0:
            raise ValueError("period_seconds must be positive")

    def _prune(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self.period_seconds:
            self._calls.popleft()

    def remaining(self) -> int:
        now = self.clock()
        self._prune(now)
        return self.max_calls - len(self._calls)

    def wait_time(self, *, cost: int = 1) -> float:
        if cost <= 0:
            raise ValueError("cost must be positive")
        if cost > self.max_calls:
            raise ValueError("cost cannot exceed max_calls")
        now = self.clock()
        self._prune(now)
        if len(self._calls) + cost <= self.max_calls:
            return 0.0
        index = max(0, cost - self.remaining() - 1)
        oldest_needed = self._calls[index]
        return max(0.0, self.period_seconds - (now - oldest_needed))

    def check(self, *, cost: int = 1) -> None:
        wait_seconds = self.wait_time(cost=cost)
        if wait_seconds > 0:
            raise RateLimitExceeded(wait_seconds)

    def record(self, *, cost: int = 1) -> None:
        self.check(cost=cost)
        now = self.clock()
        for _ in range(cost):
            self._calls.append(now)


def batch_items(items: Iterable[T], batch_size: int) -> Iterator[list[T]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def retry_with_backoff(
    action: Callable[[], T],
    *,
    retry_exceptions: tuple[type[BaseException], ...] = (RateLimitExceeded, TimeoutError, ConnectionError),
    max_attempts: int = 3,
    base_delay_seconds: float = 0.25,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    attempt = 0
    while True:
        attempt += 1
        try:
            return action()
        except retry_exceptions:
            if attempt >= max_attempts:
                raise
            sleep_fn(base_delay_seconds * (2 ** (attempt - 1)))
