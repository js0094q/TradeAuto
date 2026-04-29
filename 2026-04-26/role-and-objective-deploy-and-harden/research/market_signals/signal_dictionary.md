# Signal Dictionary

## Executive summary
The signal library is deterministic, explainable, and research-only. Signals can support entry, exit, confirmation, or suppression, but none currently authorizes live trading.

## What was tested
Unit tests cover trend, momentum, relative strength, mean reversion, liquidity, options, crypto, regime classification, and suppression behavior.

## Data used
Synthetic series and read-only provider quote observations.

## Assumptions
Signals must use only data available at evaluation time and must return suppression reasons where applicable.

## Methodology
Each signal exposes name, category, formula, inputs, output, interpretation, useful regimes, dangerous regimes, false-positive risks, asset classes, and role.

## Results
- `moving_average_trend`: short MA minus long MA divided by long MA. Entry/confirmation/suppression for equity, ETF, crypto. Dangerous in sideways whipsaw regimes.
- `rate_of_change`: trailing price change. Entry/confirmation/exit. Dangerous after exhaustion gaps.
- `relative_strength`: asset return minus benchmark return. Confirmation/suppression for equities and ETFs. Dangerous with benchmark mismatch.
- `volume_confirmed_momentum`: momentum multiplied by relative volume. Entry/confirmation. Dangerous around auctions and volume spikes.
- `zscore_reversion`: negative z-score scaled for long reversion. Entry/exit/suppression. Dangerous in crash trends.
- `rsi_stretch`: RSI overbought/oversold stretch. Entry/exit/suppression. Dangerous in persistent trends.
- `atr_breakout`: current close move versus prior ATR. Entry/confirmation/suppression. Dangerous in false breakouts.
- `compression_ratio`: short range versus long range. Confirmation/suppression. Dangerous when quiet markets stay quiet.
- `spread_quality`: bid/ask spread score. Confirmation/suppression. Dangerous when quotes are stale or zero-sided.
- `relative_volume`: current volume versus average. Confirmation/suppression. Dangerous with bad baselines.
- `options_liquidity_score`: volume, open interest, and spread. Confirmation/suppression only. Dangerous with thin strikes.
- `iv_rank`: current IV in observed range. Confirmation/suppression only. Dangerous around earnings and short histories.
- `crypto_24_7_trend`: crypto trailing trend with spread and weekend assumptions. Entry/confirmation/suppression. Dangerous during weekend liquidity shocks.
- `classify_market_regime`: objective market regime state. Suppression/sizing research only.
- `suppression_reasons`: fail-closed reasons for disabled strategy, stale data, wide spreads, closed market, missing realtime data, or kill switch.

## What passed
Signals are deterministic and unit-tested for basic directionality, suppression, and no-lookahead behavior.

## What failed
Signals are not yet calibrated on historical or shadow data.

## Rejected strategies
Any strategy using these signals without cost-adjusted validation is rejected.

## Strategies needing more paper/shadow validation
All signal combinations need validation.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Signals can appear useful because of overfit lookbacks, data cleaning errors, or survivorship bias. Parameter perturbation is mandatory.

## Operational risk notes
Signal output must be logged with reasons. Suppression reasons should be visible in dashboards and Telegram summaries before live review.

## Next engineering actions
Persist signal observations, add provider-backed feature builders, and produce per-signal precision/decay analysis.

