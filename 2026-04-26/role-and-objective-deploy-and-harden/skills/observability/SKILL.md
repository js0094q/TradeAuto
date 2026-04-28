---
name: observability
description: Add or review logs, metrics, health checks, readiness checks, traces, alerts, and failure reports.
---

# Observability

Use this skill when changing runtime behavior, deployment, broker access, risk decisions, Telegram operations, or learning loops.

## Required Signals

- service health: `/health`
- protected readiness: `/ready`
- protected metrics: `/metrics`
- risk rejections and material rejection reasons
- kill switch state
- broker connectivity state
- Telegram alert success/failure
- deployment version and rollback target
- strategy version and promotion stage
- data freshness and stale-data rejections

## Rules

- Do not log secrets, raw headers, private keys, `.env` contents, or full tokens.
- Public endpoints must stay harmless; sensitive state belongs behind admin-token checks and Nginx controls.
- Failure logs should include enough context to reproduce without exposing credentials.
- Alerts should be actionable and identify the affected service, mode, and next validation command.

## Validation

After observability changes, run compile/tests and check that payloads remain stable for existing clients.
