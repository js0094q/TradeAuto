from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyEvidence:
    name: str
    slippage_adjusted_return: float
    symbols_tested: int
    regimes_tested: int
    trade_count: int
    max_drawdown_pct: float
    allowed_drawdown_pct: float
    parameter_stability: float
    outlier_regime_dependency: bool
    data_quality_gaps: bool
    realtime_data_available: bool
    explainable_entry: bool
    explainable_avoidance: bool
    execution_assumptions_realistic: bool
    bounded_risk: bool
    kill_switch_can_respond_before_max_loss: bool
    independently_disableable: bool
    requires_manual_interpretation: bool
    stale_data_fails_closed: bool
    turnover: float
    max_turnover: float
    spread_liquidity_passed: bool
    no_trade_conditions_defined: bool


@dataclass(frozen=True)
class RejectionDecision:
    rejected: bool
    reasons: tuple[str, ...]


def evaluate_rejection(evidence: StrategyEvidence) -> RejectionDecision:
    reasons: list[str] = []
    if evidence.slippage_adjusted_return <= 0:
        reasons.append("performance disappears after realistic slippage")
    if evidence.symbols_tested < 5:
        reasons.append("performance depends on too few symbols")
    if evidence.regimes_tested < 3:
        reasons.append("performance depends on too few market regimes")
    if evidence.trade_count < 100:
        reasons.append("trade count is too small to trust")
    if evidence.max_drawdown_pct > evidence.allowed_drawdown_pct:
        reasons.append("drawdown exceeds allowed live envelope")
    if evidence.parameter_stability < 0.70:
        reasons.append("performance collapses under parameter perturbation")
    if evidence.outlier_regime_dependency:
        reasons.append("positive results only appear during outlier regimes")
    if evidence.data_quality_gaps:
        reasons.append("strategy trades during known data-quality gaps")
    if not evidence.realtime_data_available:
        reasons.append("required data is unavailable in real time")
    if not evidence.explainable_entry:
        reasons.append("strategy cannot explain why it entered")
    if not evidence.explainable_avoidance:
        reasons.append("strategy cannot explain why it avoided a trade")
    if not evidence.execution_assumptions_realistic:
        reasons.append("execution assumptions are unrealistic")
    if not evidence.bounded_risk:
        reasons.append("risk cannot be bounded")
    if not evidence.kill_switch_can_respond_before_max_loss:
        reasons.append("loss can exceed max daily loss before kill switch can respond")
    if not evidence.independently_disableable:
        reasons.append("strategy cannot be disabled independently")
    if evidence.requires_manual_interpretation:
        reasons.append("strategy requires manual interpretation")
    if not evidence.stale_data_fails_closed:
        reasons.append("strategy fails under stale data")
    if evidence.turnover > evidence.max_turnover:
        reasons.append("strategy creates excessive turnover")
    if not evidence.spread_liquidity_passed:
        reasons.append("strategy fails spread/liquidity checks")
    if not evidence.no_trade_conditions_defined:
        reasons.append("strategy lacks clear no-trade conditions")
    return RejectionDecision(rejected=bool(reasons), reasons=tuple(reasons))

