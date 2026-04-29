from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostAssumptions:
    name: str
    commission_per_trade: float = 0.0
    sec_fee_bps_on_sell: float = 0.0
    taf_fee_per_share_on_sell: float = 0.0
    spread_bps: float = 1.0
    slippage_bps: float = 1.0
    rejected_fill_rate: float = 0.0
    latency_bps: float = 0.0


BASE_COST_CASE = CostAssumptions("base", spread_bps=1.0, slippage_bps=1.0)
MODERATE_COST_CASE = CostAssumptions("moderate", spread_bps=3.0, slippage_bps=3.0, rejected_fill_rate=0.01, latency_bps=1.0)
HIGH_COST_CASE = CostAssumptions("high", spread_bps=8.0, slippage_bps=6.0, rejected_fill_rate=0.03, latency_bps=2.0)
STRESS_COST_CASE = CostAssumptions("stress", spread_bps=15.0, slippage_bps=12.0, rejected_fill_rate=0.08, latency_bps=5.0)


def bps_cost(notional: float, bps: float) -> float:
    return abs(notional) * bps / 10_000.0


def estimate_round_trip_cost(notional: float, quantity: float, *, sell_notional: float | None = None, assumptions: CostAssumptions) -> float:
    exit_notional = abs(notional if sell_notional is None else sell_notional)
    entry_notional = abs(notional)
    execution_bps = assumptions.spread_bps + assumptions.slippage_bps + assumptions.latency_bps
    entry_cost = assumptions.commission_per_trade + bps_cost(entry_notional, execution_bps)
    exit_cost = assumptions.commission_per_trade + bps_cost(exit_notional, execution_bps)
    sec_fee = bps_cost(exit_notional, assumptions.sec_fee_bps_on_sell)
    taf_fee = abs(quantity) * assumptions.taf_fee_per_share_on_sell
    rejection_penalty = (entry_notional + exit_notional) * assumptions.rejected_fill_rate * 0.0001
    return entry_cost + exit_cost + sec_fee + taf_fee + rejection_penalty

