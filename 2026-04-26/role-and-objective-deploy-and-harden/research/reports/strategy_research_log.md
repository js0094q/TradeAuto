# Strategy Research Log
Generated: 2026-04-29T04:10:32.213463+00:00
## Iteration 1
- Discovery set: ETF trend/regime rotation, opening range breakout, ETF mean reversion, crypto momentum breakout, cross-market high-beta equity confirmation.
- Improvement cycle: compared baseline ETF rotation vs BTC/ETH-confirmed high-beta overlay; compared crypto momentum with and without weekend participation.
- Parameter ranges tested: ETF top positions {3}, realized-vol cap {2.5%, 3.0%}; crypto weekend filter {off, on}.
## Outcome Summary
- `cross_market_high_beta_confirmation_v1`: score 91.8, avg return 1.06%, paper_validate.
- `liquid_etf_mean_reversion_v1`: score 91.7, avg return 0.48%, paper_validate.
- `equity_etf_trend_regime_v1`: score 90.6, avg return 3.03%, paper_validate.
- `crypto_momentum_volatility_expansion_v1`: score 65.5, avg return -0.80%, rejected: failed at least half of research windows.
- `opening_range_breakout_v1`: score 10.9, avg return -24.24%, rejected: failed at least half of research windows.
