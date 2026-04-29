# Risk Control Mapping

## Executive summary
The existing risk engine already enforces key live controls. Research code did not modify these controls and should map every strategy to them before review.

## What was tested
Existing risk tests were inspected; new tests do not alter risk behavior.

## Data used
`src/trading_system/trading/risk.py`, `src/trading_system/config.py`, and `policies/live-trading-rules.md`.

## Assumptions
Research strategies must fit existing risk envelopes rather than increasing limits.

## Methodology
Map each strategy to max position size, max order notional, max daily trades, max open positions, max daily loss, max total drawdown, cooldowns, kill switch, stale data, market closed, API failure, WebSocket failure, Telegram alerting, and dashboard fields.

## Results
Existing controls include max trades per day, max open positions, max order notional, max position notional, max daily loss, max total drawdown, max account risk percent, limit-order requirement, market-order gate, short gate, options gate, crypto gate, spread maximum, duplicate prevention, cooldown, consecutive-loss lockout, and kill switch.

## What passed
The risk engine fails orders closed when critical state is unsafe.

## What failed
Strategy-specific stale-data, WebSocket, Telegram, and dashboard mappings are not yet implemented.

## Rejected strategies
Any strategy requiring market orders, short selling, options trading, crypto trading, larger limits, or manual interpretation is rejected unless separately approved and validated.

## Strategies needing more paper/shadow validation
All strategies.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Risk engine checks an order request; it does not prove signal quality or prevent bad strategy logic unless strategy outputs are routed through it.

## Operational risk notes
Do not modify live risk limits in research work. Do not add order paths from strategy modules.

## Next engineering actions
Add read-only strategy/risk status views, log suppression reasons, and test stale-data and kill-switch behavior for each candidate.

