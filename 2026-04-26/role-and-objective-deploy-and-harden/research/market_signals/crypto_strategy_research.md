# Crypto Strategy Research

## Executive summary
Crypto research is separate from equities. The system now has a crypto signal that includes 24/7 behavior, spread suppression, and weekend liquidity assumptions. No crypto trading was enabled.

## What was tested
Unit tests verify that `crypto_24_7_trend` suppresses wide crypto spreads. Provider validation ran BTC/USD and ETH/USD historical daily bars across the required regime windows.

## Data used
Synthetic crypto prices, read-only BTC/USD and ETH/USD snapshots, and provider-backed BTC/USD and ETH/USD historical bars.

## Assumptions
Crypto has 24/7 sessions, different liquidity, different spread behavior, different drawdown windows, and separate position-sizing requirements.

## Methodology
The first crypto signal evaluates trailing trend persistence and suppresses when spread exceeds a crypto-specific maximum.

## Results
BTC/USD and ETH/USD provider snapshots and historical bars are available. The first daily-bar crypto trend breakout pass generated positive aggregate cost-adjusted results but remains `shadow_ready` because spread/liquidity and 24/7 monitoring evidence are incomplete.

## What passed
Crypto research is code-separated and does not reuse equity market-hours logic.

## What failed
No weekend liquidity study, correlation study, exchange/session limitation report, or real-time spread capture has been completed.

## Rejected strategies
Crypto strategies are rejected for restricted-live status. `crypto_trend_breakout_v1` is eligible for shadow validation only.

## Strategies needing more paper/shadow validation
24/7 trend following, volatility clustering breakout, crypto mean reversion, and weekend liquidity suppression.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Crypto can gap through stops via fast moves, exchange-specific liquidity, or outages even without equity-style sessions.

## Operational risk notes
Keep `ALLOW_CRYPTO_TRADING=false`. Crypto needs separate max loss, size, spread, stale-data, and weekend controls.

## Next engineering actions
Run BTC/ETH/SOL historical tests, add weekend/overnight drawdown reports, and compare crypto signal behavior to SPY/QQQ risk proxies.
