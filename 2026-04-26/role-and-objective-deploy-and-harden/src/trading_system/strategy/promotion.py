from __future__ import annotations

from dataclasses import dataclass

from trading_system.strategy.base import PromotionStage


@dataclass(frozen=True)
class PromotionEvidence:
    unit_tests_passed: bool = False
    backtest_passed: bool = False
    walk_forward_passed: bool = False
    paper_execution_passed: bool = False
    risk_validation_passed: bool = False
    order_logging_passed: bool = False
    telegram_alert_passed: bool = False
    kill_switch_passed: bool = False


@dataclass(frozen=True)
class PromotionDecision:
    eligible_stage: PromotionStage
    approved: bool
    missing: tuple[str, ...]


def evaluate_promotion(evidence: PromotionEvidence) -> PromotionDecision:
    missing: list[str] = []
    for name, passed in evidence.__dict__.items():
        if not passed:
            missing.append(name)

    if missing:
        if not evidence.backtest_passed:
            stage = PromotionStage.RESEARCH_ONLY
        elif not evidence.paper_execution_passed:
            stage = PromotionStage.BACKTEST_ELIGIBLE
        else:
            stage = PromotionStage.TEST_EXECUTION_ELIGIBLE
        return PromotionDecision(stage, False, tuple(missing))

    return PromotionDecision(PromotionStage.RESTRICTED_LIVE_ELIGIBLE, True, ())

