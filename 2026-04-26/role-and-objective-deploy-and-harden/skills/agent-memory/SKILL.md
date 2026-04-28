---
name: agent-memory
description: Implement durable event, decision, outcome, and lesson memory without storing secrets or allowing memory to bypass policy.
---

# Agent Memory

Use this skill when adding durable logs, summaries, retrieval memory, or memory-backed agent behavior.

## Storage Layout

- `memory/events`: raw append-only event logs
- `memory/decisions`: trading, deployment, and operator decisions
- `memory/outcomes`: measured results and post-action outcomes
- `memory/lessons`: reviewed summaries safe for retrieval

Runtime memory artifacts should be generated locally or on the VPS and should not contain secrets.

## Minimum Event Fields

Use JSONL for append-only records where possible:

```json
{"ts":"ISO-8601","event_type":"decision","actor":"agent","mode":"paper","summary":"...","correlation_id":"..."}
```

For trading outcomes, include strategy version, symbol, order ID or client order ID, risk decision, slippage, P/L, drawdown, and data source freshness when available.

## Guardrails

- Memory may inform proposals; it may not override `policies/`.
- Do not store API keys, tokens, passwords, private keys, account secrets, or raw `.env` content.
- Redact order/account identifiers if they are not needed for replay.
- Keep learning summaries separate from immutable safety rules.
