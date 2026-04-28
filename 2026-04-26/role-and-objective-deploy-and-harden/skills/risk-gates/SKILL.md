---
name: risk-gates
description: Enforce kill switch, order limits, drawdown caps, confirmation gates, audit logs, and live-trading controls.
---

# Risk Gates

Use this skill for order execution, risk limits, live enablement, kill switch behavior, strategy promotion, or operator controls.

## Non-Negotiable Gates

- Kill switch blocks trading until explicitly disabled through the protected path.
- Live mode requires `TRADING_MODE=live`, `LIVE_TRADING_ENABLED=true`, and `ALPACA_BASE_URL=https://api.alpaca.markets`.
- Non-live modes must not point to the live Alpaca endpoint.
- Required risk limits must be present and positive.
- Limit orders are required in live mode unless the user explicitly approves a policy change.
- Market orders, short selling, options, crypto, cancel-all, close-all, and resume behavior require explicit gates.
- Telegram dangerous commands require admin chat ID allowlisting.
- Destructive or financial actions require audit logs.

## Implementation Pattern

Risk checks should return structured decisions with approval state and reasons. Do not collapse risk rejections into generic errors when the reason is material.

## Tests

Add tests for every weakened or changed gate. At minimum cover:
- kill switch rejection
- endpoint/mode mismatch
- max daily loss
- max order notional
- market order default rejection
- duplicate order prevention
- live startup validation
