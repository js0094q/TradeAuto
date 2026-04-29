from __future__ import annotations


def suppression_reasons(
    *,
    data_is_stale: bool = False,
    spread_pct: float | None = None,
    max_spread_pct: float = 0.25,
    market_is_open: bool = True,
    realtime_data_available: bool = True,
    kill_switch_enabled: bool = False,
    strategy_enabled: bool = False,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if kill_switch_enabled:
        reasons.append("kill switch is enabled")
    if not strategy_enabled:
        reasons.append("strategy is disabled by default")
    if data_is_stale:
        reasons.append("data is stale")
    if spread_pct is not None and spread_pct > max_spread_pct:
        reasons.append("spread above maximum")
    if not market_is_open:
        reasons.append("market is not open for this asset class")
    if not realtime_data_available:
        reasons.append("required real-time data is unavailable")
    return tuple(reasons)

