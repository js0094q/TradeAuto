from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    stored_at: float
    ttl_seconds: float

    def is_stale(self, now: float) -> bool:
        return now - self.stored_at > self.ttl_seconds


class ResearchCache:
    def __init__(self, *, default_ttl_seconds: float = 60.0, clock: Callable[[], float] = time.time) -> None:
        if default_ttl_seconds <= 0:
            raise ValueError("default_ttl_seconds must be positive")
        self.default_ttl_seconds = default_ttl_seconds
        self.clock = clock
        self._entries: dict[str, CacheEntry[object]] = {}

    def set(self, key: str, value: object, *, ttl_seconds: float | None = None) -> None:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._entries[key] = CacheEntry(value=value, stored_at=self.clock(), ttl_seconds=ttl)

    def get(self, key: str, default: object | None = None) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return default
        if entry.is_stale(self.clock()):
            self._entries.pop(key, None)
            return default
        return entry.value

    def is_stale(self, key: str) -> bool:
        entry = self._entries.get(key)
        return entry is None or entry.is_stale(self.clock())

    def get_or_set(self, key: str, factory: Callable[[], object], *, ttl_seconds: float | None = None) -> object:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def delete(self, key: str) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()


def cache_key(*parts: object) -> str:
    return ":".join(str(part).strip().lower().replace(" ", "_") for part in parts if str(part).strip())

