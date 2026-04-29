# Execution Assumptions

## Executive summary
Backtests must model commissions, regulatory fees, spread, slippage, rejected fills, partial/delayed fills, latency, liquidity caps, and asset-class differences. The code now includes base, moderate, high, and stress cost cases.

## What was tested
Unit tests verify that stress costs exceed base costs and that buy fills move up while sell fills move down under slippage assumptions.

## Data used
Synthetic notional and trade examples.

## Assumptions
Alpaca equities may have zero commissions, but spread, slippage, latency, rejected fills, and regulatory fees still matter. Options and crypto require separate assumptions.

## Methodology
Cost cases are defined in `src/trading_system/research/backtesting/costs.py`; fill adjustments are defined in `slippage.py`.

## Results
Base case: 1 bps spread and 1 bps slippage. Moderate case: 3 bps spread, 3 bps slippage, 1% rejected fills, 1 bps latency. High case: 8 bps spread, 6 bps slippage, 3% rejected fills, 2 bps latency. Stress case: 15 bps spread, 12 bps slippage, 8% rejected fills, 5 bps latency.

## What passed
The model can subtract round-trip costs and report cost-adjusted metrics.

## What failed
No empirical fill-quality dataset exists yet.

## Rejected strategies
Any strategy whose edge disappears under moderate or high costs must be rejected.

## Strategies needing more paper/shadow validation
All strategies need shadow-time spread, slippage, and rejection estimates.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Historical bars hide queue position, partial fills, route behavior, and real quote instability.

## Operational risk notes
Opening-minute and closing-minute trades need stricter assumptions. Options spreads may be too wide for execution. Crypto weekend spreads need separate caps.

## Next engineering actions
Record real-time bid/ask/mid/last at signal time, estimate slippage from paper/shadow exits, and reject strategies that fail execution realism.

