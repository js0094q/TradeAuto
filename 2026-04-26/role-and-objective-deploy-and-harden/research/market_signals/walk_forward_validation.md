# Walk-Forward Validation

This pass uses parameter-fixed, regime-segmented walk-forward checks. It is useful for first promotion decisions but does not replace full train/validation/test optimization controls.

| Strategy | Provider Windows | Positive Test Windows | Assessment |
| --- | --- | --- | --- |
| etf_time_series_momentum_v1 | 5 | 4 | pass |
| cross_sectional_momentum_rotation_v1 | 5 | 1 | needs more validation |
| crypto_trend_breakout_v1 | 5 | 4 | pass |
| opening_range_breakout_v1 | 0 | 0 | needs more validation |
| vwap_mean_reversion_v1 | 0 | 0 | needs more validation |
| post_earnings_drift_v1 | 0 | 0 | needs more validation |

Restricted-live review still requires paper/shadow execution logs, spread evidence, latency sensitivity, Telegram alert validation, dashboard visibility, and kill-switch validation.
