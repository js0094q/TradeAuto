# Strategy Family Review

## Executive summary
Seven strategy families were documented for research: trend/momentum, breakout/volatility expansion, mean reversion, liquidity/microstructure filters, event/catalyst filters, options-derived confirmation, and crypto-specific strategies. None is eligible for restricted live-candidate review.

## What was tested
The repo already contained strategy family stubs. This pass added explainable signal modules, rejection rules, scorecards, and a provider-backed daily-bar validation runner for ETF/momentum and crypto families.

## Data used
Repository strategy registry, synthetic unit-test data, read-only provider samples, and historical Alpaca daily bars.

## Assumptions
Backtest profitability alone is insufficient. Every family must pass multi-symbol, multi-regime, cost-adjusted, out-of-sample, walk-forward, and shadow validation.

## Methodology
Each family is evaluated by hypothesis, market rationale, asset class, data requirements, signal formula, entry, exit, holding period, risk controls, favorable regime, unfavorable regime, failure modes, backtest design, and live-readiness score.

## Results
Trend/momentum: plausible in risk-on regimes but vulnerable to reversal and crowding. Current status: `shadow_ready`; restricted-live score remains below threshold.

Breakout/volatility expansion: plausible after compression or opening ranges but vulnerable to false breaks and spread spikes. Current status: `shadow_ready`; intraday provider validation required.

Mean reversion: plausible in liquid ETFs and range-bound regimes but dangerous during crashes and catalyst trends. Current status: `shadow_ready`; intraday VWAP/trend-day validation required.

Liquidity/microstructure filters: useful as suppression filters, not standalone alpha. Live-readiness score: 1/5 as controls only.

Event/catalyst filters: required for suppression; data source not wired. Live-readiness score: 0/5.

Options-derived confirmation: useful only as equity confirmation or risk filter until options execution is separately validated. A SPY option-chain sample is retrievable, but live-readiness score remains 0/5 for execution.

Crypto-specific strategies: must be separate because of 24/7 sessions and weekend liquidity. Current status: `shadow_ready`; spread/liquidity and monitoring evidence still block paper promotion.

## What passed
Signal functions and controls are deterministic and explainable. ETF, cross-sectional momentum, and crypto daily-bar research can now run from provider data.

## What failed
No family has shadow execution logs, Telegram/dashboard evidence, kill-switch exercises, or restricted-live operational validation.

## Rejected strategies
All families are rejected for live-candidate status at this time.

## Strategies needing more paper/shadow validation
Trend/momentum, compression breakout, ETF mean reversion, liquidity filters, options confirmation, and crypto trend need staged research.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Promising signals may be false alpha from survivorship bias, concentrated symbols, unmodeled spread, or overfit parameters.

## Operational risk notes
Every family must default disabled and be independently disableable before any live-candidate review.

## Next engineering actions
Add intraday provider runners, record shadow signals, wire operator visibility, and update rejection/scorecard evidence only from reproducible outputs.
