# Data Source Audit

## Executive summary
Algo Trader Plus/Alpaca data is now wired into a read-only research adapter and validation runner. Historical daily bars, latest quote/trade/snapshot shapes, crypto bars, and a SPY option-chain sample were validated without touching order endpoints or live flags.

## What was tested
Read-only provider access was sampled for asset metadata, latest snapshots, historical multi-symbol bars with pagination, crypto bars, and option-chain payloads. No account, order, or live route was touched.

## Data used
Alpaca CLI samples and provider-backed validation on April 29, 2026 UTC: stock bars, crypto bars, latest quotes/trades/snapshots, and 100 SPY option-chain contracts.

## Assumptions
Historical research jobs should use authenticated Alpaca/Algo Trader Plus market-data APIs through `src/trading_system/data/alpaca_provider.py` and `src/trading_system/data/provider.py` with batching, pagination, local caching, and rate-limit guards. Latest snapshots are useful for smoke checks but not sufficient for final execution assumptions.

## Methodology
The audit checked asset class, active/tradable status, quote availability, spread visibility, daily/minute bars, and crypto 24/7 behavior.

## Results
SPY is active, tradable, ARCA-listed, option-enabled, fractionable, and overnight-tradable. BTC/USD is active crypto, tradable, fractionable, and margin-disabled. Snapshot sampling showed that after-hours or venue-limited quotes can include poor or zero quote fields, such as an AAPL sample with a zero ask. That reinforces stale-data and invalid-quote suppression.

## What passed
Provider metadata, latest quote/trade/snapshot shapes, historical daily stock bars, historical crypto bars, option-chain snapshots, pagination, and cache-backed retrieval are available for research. Crypto data reports 24/7 timestamps separate from equity market hours.

## What failed
Corporate-action handling, survivorship-bias controls, point-in-time universe membership, persistent WebSocket capture, and a full options-liquidity surface still need deeper implementation.

## Rejected strategies
No strategy can be accepted from latest snapshots alone.

## Strategies needing more paper/shadow validation
All strategies need historical and real-time data collection before promotion.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Provider snapshots can be venue-limited, after-hours, delayed, stale, or missing sides of the quote. Historical bars must be adjusted and aligned before calculating signals.

## Operational risk notes
Use market-data APIs only. Do not use account or order endpoints for research. Do not store credentials in reports, caches, or logs.

## Next engineering actions
Normalize point-in-time universes by asset class, persist cache manifests, record quote quality in shadow validation, and add WebSocket storage for real-time monitoring.
