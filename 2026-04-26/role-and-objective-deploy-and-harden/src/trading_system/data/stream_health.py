from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamStatus:
    connected: bool
    healthy: bool
    stale: bool
    reconnect_required: bool
    data_age_seconds: float | None
    heartbeat_age_seconds: float | None
    reconnect_attempts: int
    last_error: str | None = None


class StreamHealthMonitor:
    def __init__(
        self,
        *,
        max_data_age_seconds: float = 10.0,
        max_heartbeat_age_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_data_age_seconds <= 0 or max_heartbeat_age_seconds <= 0:
            raise ValueError("stream health thresholds must be positive")
        self.max_data_age_seconds = max_data_age_seconds
        self.max_heartbeat_age_seconds = max_heartbeat_age_seconds
        self.clock = clock
        self.connected = False
        self.last_message_at: float | None = None
        self.last_heartbeat_at: float | None = None
        self.reconnect_attempts = 0
        self.last_error: str | None = None

    def mark_connected(self) -> None:
        now = self.clock()
        self.connected = True
        self.last_heartbeat_at = now
        self.last_error = None

    def record_message(self) -> None:
        self.last_message_at = self.clock()

    def record_heartbeat(self) -> None:
        self.last_heartbeat_at = self.clock()

    def mark_disconnected(self, reason: str | None = None) -> None:
        self.connected = False
        self.last_error = reason

    def mark_reconnect_attempt(self) -> None:
        self.reconnect_attempts += 1

    def status(self) -> StreamStatus:
        now = self.clock()
        data_age = None if self.last_message_at is None else now - self.last_message_at
        heartbeat_age = None if self.last_heartbeat_at is None else now - self.last_heartbeat_at
        stale = data_age is None or data_age > self.max_data_age_seconds
        heartbeat_stale = heartbeat_age is None or heartbeat_age > self.max_heartbeat_age_seconds
        reconnect_required = (not self.connected) or heartbeat_stale
        healthy = self.connected and not stale and not heartbeat_stale and self.last_error is None
        return StreamStatus(
            connected=self.connected,
            healthy=healthy,
            stale=stale,
            reconnect_required=reconnect_required,
            data_age_seconds=data_age,
            heartbeat_age_seconds=heartbeat_age,
            reconnect_attempts=self.reconnect_attempts,
            last_error=self.last_error,
        )

