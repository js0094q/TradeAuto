from __future__ import annotations

from trading_system.data.stream_health import StreamHealthMonitor, StreamStatus


class ResearchStreamMonitor:
    def __init__(self, health: StreamHealthMonitor | None = None) -> None:
        self.health = health or StreamHealthMonitor()

    def on_connect(self) -> None:
        self.health.mark_connected()

    def on_message(self) -> None:
        self.health.record_message()

    def on_heartbeat(self) -> None:
        self.health.record_heartbeat()

    def on_disconnect(self, reason: str) -> None:
        self.health.mark_disconnected(reason)
        self.health.mark_reconnect_attempt()

    def status(self) -> StreamStatus:
        return self.health.status()

