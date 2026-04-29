from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SignalObservation:
    timestamp: str
    symbol: str
    asset_class: str
    bid: float | None
    ask: float | None
    mid: float | None
    last_price: float | None
    spread_pct: float | None
    volume: float | None
    relative_volume: float | None
    signal_state: str
    regime_state: str
    would_enter: bool
    suppressed: bool
    suppression_reason: str | None
    theoretical_entry_price: float | None
    theoretical_exit_price: float | None
    realized_paper_result: float | None
    estimated_slippage: float | None
    latency_estimate_ms: float | None
    data_freshness_seconds: float | None
    data_source_health: str


class SignalRecorder:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.observations: list[SignalObservation] = []

    def record(self, observation: SignalObservation) -> None:
        self.observations.append(observation)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(observation), sort_keys=True) + "\n")

    def summary(self) -> dict[str, Any]:
        total = len(self.observations)
        suppressed = sum(1 for item in self.observations if item.suppressed)
        entered = sum(1 for item in self.observations if item.would_enter)
        spreads = [item.spread_pct for item in self.observations if item.spread_pct is not None]
        return {
            "observations": total,
            "would_enter": entered,
            "suppressed": suppressed,
            "average_spread_pct": sum(spreads) / len(spreads) if spreads else None,
            "suppression_reasons": sorted({item.suppression_reason for item in self.observations if item.suppression_reason}),
        }

