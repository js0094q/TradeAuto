# Live Candidate Scorecard

## Executive summary
The scorecard framework was implemented in `src/trading_system/research/scorecard.py`, and the provider validation runner now generates evidence-backed strategy status reports. No strategy meets restricted-live readiness.

## What was tested
Unit tests verify the 35/45 threshold, mandatory minimums, and default-disabled requirement.

## Data used
Synthetic scorecard unit tests, registry strategy stage values, read-only Alpaca daily bars, and the generated provider validation manifest.

## Assumptions
A scorecard is only valid when populated from reproducible evidence, not judgment alone.

## Methodology
Strategies score 0 to 5 on signal rationale, data quality, robustness, regime stability, execution realism, risk containment, explainability, operational simplicity, and failure safety. Minimum total is 35. Mandatory dimensions requiring at least 4 are data quality, robustness, execution realism, risk containment, and failure safety.

## Results
Generated status results:
- `etf_time_series_momentum_v1`: `shadow_ready`.
- `cross_sectional_momentum_rotation_v1`: `shadow_ready`.
- `opening_range_breakout_v1`: `shadow_ready`.
- `vwap_mean_reversion_v1`: `shadow_ready`.
- `crypto_trend_breakout_v1`: `shadow_ready`.
- `post_earnings_drift_v1`: `needs_data`.

The detailed score table is in `strategy_scorecard.md`.

## What passed
Scorecard threshold logic is implemented and tested. Evidence-backed status generation now runs from `scripts/research/run_provider_validation.py`.

## What failed
No strategy has the required paper/shadow execution logs, monitoring evidence, spread/latency validation, and kill-switch exercise needed for restricted-live review.

## Rejected strategies
All strategies are rejected for restricted live-candidate review.

## Strategies needing more paper/shadow validation
All shadow-ready strategy families listed in `ready_strategy_validation.md`.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Score inflation is a risk. Mandatory categories should be supported by run artifacts and reviewed before promotion.

## Operational risk notes
Restricted live-candidate review is not unrestricted live trading. Live activation still requires explicit env flags, control-plane authorization, and operations checklist completion.

## Next engineering actions
Run shadow monitoring, collect Telegram/dashboard evidence, add intraday and earnings data, and rerun scorecards after paper/shadow artifacts exist.
