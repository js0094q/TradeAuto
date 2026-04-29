from __future__ import annotations

from dataclasses import dataclass, field


SCORECARD_DIMENSIONS = (
    "signal_rationale",
    "data_quality",
    "robustness",
    "regime_stability",
    "execution_realism",
    "risk_containment",
    "explainability",
    "operational_simplicity",
    "failure_safety",
)

MANDATORY_MINIMUMS = {
    "data_quality": 4,
    "robustness": 4,
    "execution_realism": 4,
    "risk_containment": 4,
    "failure_safety": 4,
}


@dataclass(frozen=True)
class StrategyScorecard:
    strategy_name: str
    scores: dict[str, int]
    strategy_default_disabled: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        missing = set(SCORECARD_DIMENSIONS) - set(self.scores)
        extra = set(self.scores) - set(SCORECARD_DIMENSIONS)
        if missing:
            raise ValueError("missing scorecard dimensions: " + ", ".join(sorted(missing)))
        if extra:
            raise ValueError("unknown scorecard dimensions: " + ", ".join(sorted(extra)))
        invalid = {name: value for name, value in self.scores.items() if value < 0 or value > 5}
        if invalid:
            raise ValueError("scorecard values must be between 0 and 5")

    @property
    def total_score(self) -> int:
        return sum(self.scores.values())

    @property
    def mandatory_failures(self) -> tuple[str, ...]:
        failures = [name for name, minimum in MANDATORY_MINIMUMS.items() if self.scores[name] < minimum]
        if not self.strategy_default_disabled:
            failures.append("strategy default-disabled control missing")
        return tuple(failures)

    @property
    def eligible_for_restricted_live_review(self) -> bool:
        return self.total_score >= 35 and not self.mandatory_failures


def empty_research_scorecard(strategy_name: str) -> StrategyScorecard:
    return StrategyScorecard(strategy_name=strategy_name, scores={name: 0 for name in SCORECARD_DIMENSIONS})
