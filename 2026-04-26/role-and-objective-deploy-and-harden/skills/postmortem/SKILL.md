---
name: postmortem
description: Summarize failures, root cause, blast radius, fixes, regression tests, and follow-up gates after incidents or failed runs.
---

# Postmortem

Use this skill after deployment failures, service outages, rejected live gates, unexpected broker behavior, bad strategy outcomes, or failed tests.

## Format

```text
Summary:
Impact:
Timeline:
Root Cause:
Detection:
Resolution:
Regression Tests:
Remaining Risk:
Follow-Up:
```

## Rules

- Lead with facts from logs, tests, health checks, or command output.
- Do not speculate beyond evidence without labeling it.
- Include exact file paths, service names, command names, and timestamps when available.
- For trading incidents, include mode, strategy version, order/client order IDs if safe, risk decision, P/L, drawdown, and kill switch state.
- Convert durable lessons into `memory/lessons` only after secrets are removed and the lesson does not weaken policy.
