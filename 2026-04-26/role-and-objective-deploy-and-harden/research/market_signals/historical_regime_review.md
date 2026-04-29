# Historical Regime Review

## Executive summary
The research program now has an initial provider-backed daily-bar validation pass across 2018, 2020, 2021, 2022, 2023, 2024, and 2025-2026 regimes. The evidence is sufficient for controlled shadow validation, not restricted live review.

## What was tested
The provider validation runner pulled read-only Alpaca historical bars for ETF/equity and crypto universes, grouped results by regime, and generated cost-adjusted metrics and fixed-parameter walk-forward summaries.

## Data used
Read-only Alpaca CLI daily bars, regime definitions, repository source, and synthetic unit-test fixtures.

## Assumptions
Historical data must be adjusted, point-in-time, symbol-aware, and split into train, validation, and test periods without lookahead.

## Methodology
Each regime should evaluate trend, mean reversion, breakout, volatility expansion, gap behavior, liquidity behavior, false-positive rate, drawdown, signal decay, spread/slippage sensitivity, and suppression rules.

## Results
Required regimes:
- 2018 volatility shock: volatility stress.
- 2020 COVID crash: crash and liquidity stress.
- 2020 rebound: momentum and volatility rebound.
- 2021 liquidity/momentum period: high-risk appetite.
- 2022 rate-hike bear market: bear trend and multiple compression.
- 2023 mega-cap/AI concentration: narrow leadership.
- 2024 recent market structure: post-2022 normalization.
- 2025-2026 recent behavior: current regime relevance.

## What passed
The code now supports regime labels, per-regime metric grouping, provider-backed daily-bar ingestion, pagination, and generated validation reports.

## What failed
No strategy passed restricted-live validation. ETF and cross-sectional daily strategies showed regime-specific positive periods but did not pass aggregate cost-adjusted paper promotion. Intraday ORB/VWAP and post-earnings drift remain data-incomplete.

## Rejected strategies
Strategies that only work in 2021 momentum or 2023 mega-cap concentration should be rejected until they pass broader testing.

## Strategies needing more paper/shadow validation
ETF time-series momentum, cross-sectional momentum rotation, crypto trend breakout, opening-range breakout, and VWAP mean reversion are ready for shadow validation.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Regime labels can overfit. Use objective formulas, keep labels stable before testing, and reserve final out-of-sample periods.

## Operational risk notes
High-volatility and crash regimes should suppress or shrink strategies unless execution quality is proven.

## Next engineering actions
Add intraday provider pulls, perturb parameters, persist rejected periods and symbols, and connect shadow logs to Telegram/dashboard monitoring.
