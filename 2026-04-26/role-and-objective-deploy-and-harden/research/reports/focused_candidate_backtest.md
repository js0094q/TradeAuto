# Focused Candidate Backtest
Generated: 2026-04-29T04:19:51.350583+00:00

## Scope
- Research-only continuation for `equity_etf_trend_regime_v1` and `cross_market_high_beta_confirmation_v1`.
- No order submission, broker execution, risk limits, or live-trading gates were changed.
- Data path: Alpaca CLI profile `paper` using `iex` equity feed; Alpaca crypto daily bars for BTC/ETH confirmation.
- Cost path: moderate equity costs with high-cost stress re-checks.

## Results
| Strategy | Role | Variant | Trades | Avg Return | Avg Ann. Return | Avg Max DD | Robustness | Stress Delta | Recommendation |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `equity_etf_trend_regime_v1` | best default starting system | current 200SMA + 60d rotation baseline | 127 | 3.03% | 5.31% | 1.10% | 75% | 0.58% | `paper_validate` |
| `equity_etf_trend_regime_v1` | default stack refinement | 200SMA + 20/50EMA + RSI + ATR sizing + RVOL | 334 | 0.84% | 0.45% | 1.19% | 50% | 1.32% | `watchlist` |
| `cross_market_high_beta_confirmation_v1` | highest-score overlay candidate | high-beta ETF rotation gated by BTC/ETH 50d trend | 54 | 1.17% | 2.47% | 0.35% | 75% | 0.24% | `paper_validate` |

## Conclusions
- `equity_etf_trend_regime_v1` (current 200SMA + 60d rotation baseline): Eligible for paper-shadow validation only; no live promotion implied.
- `equity_etf_trend_regime_v1` (200SMA + 20/50EMA + RSI + ATR sizing + RVOL): Keep the indicator stack as an implementation blueprint, but do not replace the simpler baseline until robustness improves.
- `cross_market_high_beta_confirmation_v1` (high-beta ETF rotation gated by BTC/ETH 50d trend): Paper-validate only as an overlay on the ETF momentum stack, not as a standalone system.

## Window Detail
### equity_etf_trend_regime_v1 - current 200SMA + 60d rotation baseline
| Window | Period | Return | Max DD | Sharpe | Profit Factor | Trades | Stress Return |
|---|---|---:|---:|---:|---:|---:|---:|
| recent_short | 2026-01-01 to 2026-04-28 | 3.11% | 1.02% | 3.42 | 2.68 | 24 | 2.67% |
| medium_window | 2025-05-01 to 2026-04-28 | 8.39% | 1.08% | 3.66 | 2.82 | 68 | 7.16% |
| prior_volatile_window | 2025-02-01 to 2025-04-30 | -1.70% | 1.99% | -9.02 | 0.23 | 19 | -2.04% |
| sideways_window | 2025-06-01 to 2025-08-31 | 2.32% | 0.30% | 6.22 | 4.88 | 16 | 2.03% |
### equity_etf_trend_regime_v1 - 200SMA + 20/50EMA + RSI + ATR sizing + RVOL
| Window | Period | Return | Max DD | Sharpe | Profit Factor | Trades | Stress Return |
|---|---|---:|---:|---:|---:|---:|---:|
| recent_short | 2026-01-01 to 2026-04-28 | -0.55% | 1.24% | -1.25 | 0.76 | 51 | -1.26% |
| medium_window | 2025-05-01 to 2026-04-28 | 4.06% | 1.24% | 1.99 | 1.51 | 196 | 0.99% |
| prior_volatile_window | 2025-02-01 to 2025-04-30 | -1.49% | 1.77% | -5.61 | 0.35 | 27 | -1.94% |
| sideways_window | 2025-06-01 to 2025-08-31 | 1.33% | 0.50% | 2.65 | 1.59 | 60 | 0.30% |
### cross_market_high_beta_confirmation_v1 - high-beta ETF rotation gated by BTC/ETH 50d trend
| Window | Period | Return | Max DD | Sharpe | Profit Factor | Trades | Stress Return |
|---|---|---:|---:|---:|---:|---:|---:|
| recent_short | 2026-01-01 to 2026-04-28 | 1.37% | 0.64% | 5.14 | 2.73 | 16 | 1.08% |
| medium_window | 2025-05-01 to 2026-04-28 | 2.58% | 0.64% | 5.78 | 3.00 | 32 | 2.00% |
| prior_volatile_window | 2025-02-01 to 2025-04-30 | 0.00% | 0.00% | 0.00 | 0.00 | 0 | 0.00% |
| sideways_window | 2025-06-01 to 2025-08-31 | 0.72% | 0.10% | 13.38 | 8.38 | 6 | 0.61% |

## Paper Validation Gate
- Treat `equity_etf_trend_regime_v1` as the default build-first system only after paper-shadow daily rebalance logs exist.
- Treat `cross_market_high_beta_confirmation_v1` as an overlay candidate; it should suppress or permit high-beta ETF exposure but should not independently promote live orders.
- Add live quote spread checks before any intraday or restricted-live promotion review.
