---
name: broker-adapter
description: Add broker or market-data adapters while preserving paper/live separation, order idempotency, CLI safety, and test fixtures.
---

# Broker Adapter

Use this skill when changing Alpaca SDK code, Alpaca CLI wrappers, market data access, order submission, positions, account state, or broker diagnostics.

## Rules

- Strategy code must not submit orders directly.
- Orders must pass through risk evaluation and execution boundaries.
- Paper, test, diagnostics, and live modes must be explicit.
- Never route non-live mode to `https://api.alpaca.markets`.
- Never imply paper credentials are live credentials.
- Use `--quiet` for Alpaca CLI automation.
- Use `ALPACA_LIVE_TRADE=false` unless live trading is explicitly requested.
- Live order submission requires an idempotent `client_order_id`.
- On ambiguous failures, query by client order ID before retrying.

## Tests

Add or update tests for:
- missing credentials
- paper/live endpoint crossover
- order idempotency
- rejected live actions without explicit live flags
- structured diagnostic errors
- broker timeout or rate-limit behavior

## Validation

For read-only broker validation:

```bash
./scripts/alpaca_doctor.sh paper
./scripts/alpaca_account.sh paper
./scripts/alpaca_clock.sh paper
```

Run live checks only with explicit live intent and the real live env on the VPS.
