# Ready Strategy Validation

Provider-backed validation supports controlled shadow/paper evaluation, not live deployment. All strategy configuration remains default-disabled and live mode remains blocked by existing gates.

| Strategy | Status | Best Mode Now | Reason |
| --- | --- | --- | --- |
| etf_time_series_momentum_v1 | shadow_ready | shadow | Provider-backed evidence exists across multiple regimes, but aggregate cost-adjusted results do not yet support paper promotion. |
| cross_sectional_momentum_rotation_v1 | shadow_ready | shadow | Provider-backed evidence exists, but breadth or net-period stability is not yet enough for paper promotion. |
| crypto_trend_breakout_v1 | shadow_ready | shadow | Daily crypto bars validate signal availability; spread/liquidity and 24/7 monitoring evidence still block paper promotion. |
| opening_range_breakout_v1 | shadow_ready | shadow | Implementation is explainable and gated, but provider-backed intraday validation is still required. |
| vwap_mean_reversion_v1 | shadow_ready | shadow | Implementation is explainable and gated, but provider-backed intraday validation is still required. |
| post_earnings_drift_v1 | needs_data | research_only | Earnings surprise and revisions data are not available in the current provider adapter. |

Manual enablement still requires editing untracked runtime configuration, leaving kill switch controls intact, and validating Telegram/dashboard visibility before any paper or restricted-live run.
