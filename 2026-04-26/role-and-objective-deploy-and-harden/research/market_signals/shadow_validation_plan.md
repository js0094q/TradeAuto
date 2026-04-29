# Shadow Validation Plan

- Keep every strategy `enabled: false` until explicitly selected for shadow or paper mode.
- Start with `etf_time_series_momentum_v1` and `cross_sectional_momentum_rotation_v1` in shadow review; paper promotion requires aggregate cost-adjusted improvement and operator visibility.
- Keep `opening_range_breakout_v1` and `vwap_mean_reversion_v1` in shadow only until intraday bars, spreads, first-minute suppression, trend-day suppression, and end-of-day flat behavior are validated.
- Keep `crypto_trend_breakout_v1` in shadow only until crypto spread, weekend liquidity, 24/7 monitoring, and crypto-specific drawdown gates are proven.
- Keep `post_earnings_drift_v1` research-only until point-in-time earnings surprise data is available.
- Required operator checks before any paper run: fresh market data, kill switch readable/off only by policy, risk engine healthy, Telegram alerts working, dashboard status visible, and strategy-specific enable flag set in untracked config.
