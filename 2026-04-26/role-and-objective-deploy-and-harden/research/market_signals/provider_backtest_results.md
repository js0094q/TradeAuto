# Provider-Backed Backtest Results

Read-only Alpaca CLI data was used for historical daily bars. No order endpoints were called, and live trading was not enabled. Metrics use moderate spread/slippage assumptions and a $25 strategy notional against a $1,000 research equity base for comparability.

| Strategy | Symbols | Regimes | Trades | Slippage-Adjusted Return | Max Drawdown | Win Rate |
| --- | --- | --- | --- | --- | --- | --- |
| etf_time_series_momentum_v1 | 9 | 5 | 67 | -0.86% | 1.94% | 53.7% |
| cross_sectional_momentum_rotation_v1 | 9 | 5 | 58 | -0.85% | 1.33% | 53.4% |
| crypto_trend_breakout_v1 | 2 | 5 | 42 | 2.91% | 0.77% | 57.1% |
| opening_range_breakout_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |
| vwap_mean_reversion_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |
| post_earnings_drift_v1 | 0 | 0 | 0 | 0.00% | 0.00% | 0.0% |

Fetch gaps: none
