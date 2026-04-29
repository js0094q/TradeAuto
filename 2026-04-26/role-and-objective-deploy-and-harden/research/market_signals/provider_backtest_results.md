# Provider-Backed Backtest Results

Read-only Alpaca historical market data from the research data layer was used for daily bars. No order endpoints were called, and live trading was not enabled. Metrics use moderate spread/slippage assumptions and a $25 strategy notional against a $1,000 research equity base for comparability.

Core ETF universe for this pass: SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI.

| Strategy | Symbols | Regimes | Trades | Slippage-Adjusted Return | Max Drawdown | Win Rate |
| --- | --- | --- | --- | --- | --- | --- |
| etf_time_series_momentum_v1 | 9 | 5 | 67 | -0.86% | 2.20% | 53.7% |
| cross_sectional_momentum_rotation_v1 | 9 | 5 | 58 | -0.85% | 1.33% | 53.4% |
| crypto_trend_breakout_v1 | 2 | 5 | 42 | 2.91% | 0.77% | 57.1% |
| opening_range_breakout_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |
| vwap_mean_reversion_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |
| post_earnings_drift_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |

Fetch gaps: none

## Current Paper Positions Snapshot

| Symbol | Qty | Market Value | Side | Asset Class | Matched Strategy Universes |
| --- | --- | --- | --- | --- | --- |
| QQQ | 37.949510 | $24,987.85 | long | us_equity | cross_sectional_momentum_rotation_v1, etf_time_series_momentum_v1 |
| XLK | 158.047788 | $24,982.61 | long | us_equity | cross_sectional_momentum_rotation_v1, etf_time_series_momentum_v1 |
| XLE | 422.868817 | $24,841.43 | long | us_equity | cross_sectional_momentum_rotation_v1, etf_time_series_momentum_v1 |
| IWM | 0.003642 | $0.99 | long | us_equity | cross_sectional_momentum_rotation_v1, etf_time_series_momentum_v1 |
