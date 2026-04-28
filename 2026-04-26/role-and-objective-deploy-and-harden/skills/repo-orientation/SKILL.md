---
name: repo-orientation
description: Map this trading system's architecture, entrypoints, env files, deployment targets, safety boundaries, and validation commands before implementation work.
---

# Repo Orientation

Use this skill before broad repo changes, new features, deployment work, or unfamiliar failure triage.

## Procedure

1. Read the nearest `AGENTS.md` for the files you will touch.
2. Identify the smallest relevant file set before editing.
3. Map the affected boundary:
   - API/control: `src/trading_system/api`
   - broker access: `src/trading_system/broker`
   - risk and execution: `src/trading_system/trading`
   - strategy research and promotion: `src/trading_system/strategy`
   - Telegram operations: `src/trading_system/telegram`
   - deployment: `scripts`, `ops`, `docs`
4. Check the environment mode involved: `diagnostics`, `paper`, `test`, or `live`.
5. Confirm whether the task touches secrets, order submission, live deployment, service restarts, or destructive actions.

## Required Output

Report:
- files inspected
- boundary touched
- assumptions made
- validation command planned
- any risk control that would be weakened by the requested change
