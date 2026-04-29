# Real-Time Shadow Validation

## Executive summary
A research-only shadow-validation layer was added to record signal observations, spread, liquidity, data freshness, stream health, suppression reasons, theoretical entries/exits, and paper results. It does not place trades.

## What was tested
Stream health behavior is unit-tested. The recorder and monitor modules are importable and deterministic.

## Data used
Synthetic status data. No live WebSocket session was started.

## Assumptions
Shadow validation must run before restricted live-candidate review and must compare real-time conditions against historical assumptions.

## Methodology
`src/trading_system/research/realtime` includes stream monitor, signal recorder, spread monitor, liquidity monitor, and shadow trade result objects.

## Results
The recorder captures timestamp, symbol, asset class, bid, ask, mid, last, spread, volume, relative volume, signal state, regime state, would-enter flag, suppression flag, suppression reason, theoretical prices, paper result, slippage, latency, data freshness, and data-source health.

## What passed
The structure can fail closed on stale data and reconnect-required stream health.

## What failed
No provider WebSocket integration or persistent production storage target is configured yet.

## Rejected strategies
Any strategy without shadow observations is rejected for live-candidate review.

## Strategies needing more paper/shadow validation
All strategies.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Shadow trades may still overstate execution because they do not queue, route, or reject like real orders.

## Operational risk notes
Shadow monitoring must remain read-only and must not call order endpoints.

## Next engineering actions
Connect WebSocket streams, persist JSONL or database observations, summarize suppression rates, and compare spread/slippage observations to backtest assumptions.

