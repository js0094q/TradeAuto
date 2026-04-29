from __future__ import annotations

import unittest

from trading_system.data.stream_health import StreamHealthMonitor


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class StreamHealthTests(unittest.TestCase):
    def test_stream_health_tracks_stale_data_and_reconnects(self) -> None:
        clock = FakeClock()
        monitor = StreamHealthMonitor(max_data_age_seconds=5, max_heartbeat_age_seconds=10, clock=clock)
        monitor.mark_connected()
        monitor.record_message()
        self.assertTrue(monitor.status().healthy)
        clock.now = 6
        status = monitor.status()
        self.assertTrue(status.stale)
        self.assertFalse(status.healthy)
        monitor.mark_disconnected("socket closed")
        monitor.mark_reconnect_attempt()
        status = monitor.status()
        self.assertTrue(status.reconnect_required)
        self.assertEqual(status.reconnect_attempts, 1)
        self.assertEqual(status.last_error, "socket closed")


if __name__ == "__main__":
    unittest.main()

