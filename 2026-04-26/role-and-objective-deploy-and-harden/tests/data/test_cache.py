from __future__ import annotations

import unittest

from trading_system.data.cache import ResearchCache, cache_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class CacheTests(unittest.TestCase):
    def test_cache_expires_stale_entries(self) -> None:
        clock = FakeClock()
        cache = ResearchCache(default_ttl_seconds=5, clock=clock)
        cache.set("SPY", {"close": 100})
        self.assertEqual(cache.get("SPY"), {"close": 100})
        clock.now = 106
        self.assertIsNone(cache.get("SPY"))
        self.assertTrue(cache.is_stale("SPY"))

    def test_cache_key_is_stable(self) -> None:
        self.assertEqual(cache_key("SPY", "1 Min", "Bars"), "spy:1_min:bars")


if __name__ == "__main__":
    unittest.main()

