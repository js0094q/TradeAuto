# Backtest Validation Report

## Executive summary
A cost-aware metrics, split, walk-forward framework, and provider-backed validation runner are in place. The first pass through the read-only Alpaca historical research data layer covered the required historical regimes for daily equity/ETF and crypto bars. Results support shadow validation only; no strategy is restricted-live ready.

## What was tested
Unit tests cover cost escalation, slippage-adjusted fill prices, metrics outputs, chronological train/validation/test splits, walk-forward windows, and no-lookahead ATR behavior.

## Data used
Unit tests use synthetic fixtures. Provider validation used read-only Alpaca historical daily bars fetched through the research data layer for ETF/equity and crypto universes, plus a SPY option-chain sample for options-data availability. No account or order endpoint was called.

## Assumptions
Historical validation must include transaction costs, spread, slippage, rejected fills, latency sensitivity, per-symbol, per-regime, per-time-of-day, drawdown, exposure, turnover, and perturbation analysis.

## Methodology
`src/trading_system/research/backtesting` now includes `costs.py`, `slippage.py`, `metrics.py`, `splits.py`, `walk_forward.py`, and `reporting.py`.

## Results
Implemented metrics: total return, annualized return, Sharpe, Sortino, max drawdown, win rate, average win/loss, profit factor, expectancy, exposure time, turnover, average holding period, trade count, best/worst trade, longest losing streak, slippage-adjusted return, spread-adjusted return, by-symbol, by-regime, and by-time-of-day results.

Provider-backed daily validation results are recorded in `provider_backtest_results.md` and `provider_validation_results.json`.
- `etf_time_series_momentum_v1` (core ETF universe): 67 trades, -0.86% slippage-adjusted return, 2.20% max drawdown, 4/5 positive walk-forward windows.
- `cross_sectional_momentum_rotation_v1` (core ETF universe): 58 trades, -0.85% slippage-adjusted return, 1.33% max drawdown, 1/5 positive walk-forward windows.
- `crypto_trend_breakout_v1`: 42 trades, 2.91% slippage-adjusted return, 0.77% max drawdown.

## What passed
Framework-level tests pass for deterministic behavior. Provider-backed data retrieval through the new research data layer, pagination, caching, options-chain sampling, and report generation completed without fetch errors.

## What failed
The daily ETF and cross-sectional strategies did not produce aggregate positive cost-adjusted results under the first fixed-rule validation. Opening-range breakout and VWAP mean reversion still require intraday provider validation. Post-earnings drift still lacks point-in-time earnings data.

## Rejected strategies
Post-earnings drift remains `needs_data`. No strategy is rejected outright for shadow research based on this run.

## Strategies needing more paper/shadow validation
ETF time-series momentum, cross-sectional momentum rotation, crypto trend breakout, opening-range breakout, and VWAP mean reversion are `shadow_ready`. None should be promoted to restricted live.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Synthetic tests prove code behavior, not alpha. Historical jobs must avoid tuning on final test periods.

## Operational risk notes
Never report gross-only returns. Always show base, moderate, high, and stress cost cases.

## Next engineering actions
Add intraday bars for ORB/VWAP, point-in-time earnings data for post-earnings drift, parameter perturbation, real-time spread capture, shadow logs, Telegram/dashboard evidence, and a reproducible promotion manifest.
