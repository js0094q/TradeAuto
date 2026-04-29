from __future__ import annotations

import unittest

from trading_system.data.rate_limits import RateLimitExceeded, RateLimitGuard, batch_items, retry_with_backoff


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RateLimitTests(unittest.TestCase):
    def test_rate_limit_blocks_until_window_expires(self) -> None:
        clock = FakeClock()
        guard = RateLimitGuard(max_calls=2, period_seconds=10, clock=clock)
        guard.record()
        guard.record()
        with self.assertRaises(RateLimitExceeded) as ctx:
            guard.check()
        self.assertEqual(ctx.exception.wait_seconds, 10.0)
        clock.now = 10.0
        guard.record()
        self.assertEqual(guard.remaining(), 1)

    def test_batches_items(self) -> None:
        self.assertEqual(list(batch_items([1, 2, 3, 4, 5], 2)), [[1, 2], [3, 4], [5]])

    def test_retry_with_backoff_retries_transient_errors(self) -> None:
        calls = {"count": 0}
        sleeps: list[float] = []

        def action() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise ConnectionError("transient")
            return "ok"

        result = retry_with_backoff(action, max_attempts=3, base_delay_seconds=0.5, sleep_fn=sleeps.append)
        self.assertEqual(result, "ok")
        self.assertEqual(sleeps, [0.5, 1.0])


if __name__ == "__main__":
    unittest.main()

