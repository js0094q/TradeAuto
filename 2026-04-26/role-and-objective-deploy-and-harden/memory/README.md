# Agent Memory

Memory is durable context for autonomous and learning workflows. It is not a policy engine and must not override `policies/`, startup validation, risk gates, or human approval requirements.

## Layout

- `events/`: append-only raw event logs, usually JSONL.
- `decisions/`: decision records for trading, deployment, risk, and operator actions.
- `outcomes/`: measured results such as P/L, drawdown, slippage, fill quality, deployment status, and alert delivery.
- `lessons/`: reviewed summaries safe for retrieval.

## Data Rules

- Do not store API keys, passwords, private keys, tokens, raw `.env` values, or full secret-bearing command output.
- Redact account identifiers unless they are needed for audit replay.
- Include mode (`paper`, `test`, `diagnostics`, or `live`) on trading and broker events.
- Include strategy version, prompt/config version, and code version where available.
- Generated runtime logs are ignored by default; commit only templates or reviewed lessons when useful.

## Learning Flow

Observe -> Log -> Score -> Summarize -> Retrieve -> Propose Change -> Test -> Human/Policy Gate -> Deploy
