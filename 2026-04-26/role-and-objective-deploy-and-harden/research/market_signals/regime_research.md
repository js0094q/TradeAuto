# Regime Research

## Executive summary
An objective regime framework was added in `src/trading_system/research/signals/regime.py`. It labels risk-on, risk-off, high-volatility, and mixed regimes using index trends, realized volatility, IWM relative strength, and gap size.

## What was tested
Unit tests verify high-volatility labeling, no-trade rules, and sizing reduction.

## Data used
Synthetic test prices and required formula definitions. Provider-backed SPY, QQQ, IWM, sector breadth, volatility, and gap data remain required.

## Assumptions
Regime labels are controls, not alpha by themselves. They should suppress or size down strategies when conditions are hostile.

## Methodology
The formula compares SPY and QQQ short moving averages to long moving averages, subtracts realized-volatility pressure and gap risk, and includes optional IWM relative strength.

## Results
Risk-on: constructive index trends and relative strength. Risk-off: unfavorable index trend or volatility. High-volatility: realized volatility above stress threshold. Mixed: unclear trend, breadth, or volatility.

## What passed
Regime state returns a label, score, reasons, no-trade rules, and sizing adjustment.

## What failed
Sector breadth, VIX proxy, index dispersion, correlation regime, macro/rate proxy, and premarket direction are not yet wired to provider data.

## Rejected strategies
Any strategy without no-trade rules for high-volatility, stale data, and major gaps should be rejected.

## Strategies needing more paper/shadow validation
Trend, breakout, mean reversion, and crypto strategies need per-regime performance reporting.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Moving-average regime labels lag fast crashes. Real-time volatility and spread checks must override stale regime optimism.

## Operational risk notes
Sizing adjustments are research outputs only. They do not alter live position limits.

## Next engineering actions
Add provider-backed breadth, volatility, gap, dispersion, and correlation features; store regime labels with every signal and shadow observation.

