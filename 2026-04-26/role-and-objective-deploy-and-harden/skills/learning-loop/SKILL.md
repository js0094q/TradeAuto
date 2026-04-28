---
name: learning-loop
description: Convert observed trading or operational outcomes into scored lessons, proposals, tests, and gated changes.
---

# Learning Loop

Use this skill for autonomous improvement, strategy learning, post-run analysis, or outcome scoring.

## Loop

Observe -> Log -> Score -> Summarize -> Retrieve -> Propose Change -> Test -> Human/Policy Gate -> Deploy

## Minimum Controls

- The agent can propose strategy, prompt, parameter, or code changes.
- The agent cannot rewrite or bypass `policies/`, risk gates, approval requirements, or live-trading controls.
- Every proposed learning change needs regression tests or a documented reason tests are not applicable.
- Live trading changes require human approval, readiness validation, and rollback instructions.

## Trading Scores

Track, when applicable:
- realized and unrealized P/L
- drawdown
- slippage
- fill quality
- win rate
- expectancy
- rejected-order reasons
- data freshness
- strategy version

## Output

Produce a short learning note with:
- observation
- score or measured outcome
- proposed change
- risk impact
- tests required
- approval gate required
