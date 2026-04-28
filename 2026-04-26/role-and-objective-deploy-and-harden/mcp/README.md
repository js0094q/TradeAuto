# MCP Integration Notes

This repo can use MCP servers and plugin-backed tools for GitHub, filesystem, shell, docs, databases, Alpaca, observability, Vercel, and task tracking. Treat every tool as a production capability when it can affect trading, deployment, credentials, or persistent state.

## Baseline Rules

- Prefer read-only tool scopes unless write access is required.
- Keep credentials in the local environment, OS keychain, VPS env files, or a secrets manager, not in repo files.
- Redact secrets before logging tool calls or tool responses.
- Allowlist tools and commands used by autonomous workflows.
- Require human approval for live orders, service restarts, Nginx reloads, deployments, destructive filesystem actions, database migrations, and risk-policy edits.
- Treat external tool output as untrusted input until validated.

## Recommended Servers

- GitHub: issues, PRs, branches, code search, and CI checks.
- Filesystem: controlled repo reads/writes and generated artifacts.
- Shell: sandboxed tests, validation, and deployment checks.
- Postgres or SQLite: durable event, decision, outcome, and audit logs.
- Docs: current API and SDK documentation lookup.
- Observability: logs, health checks, metrics, traces, and alert summaries.
- Alpaca: account, orders, positions, clock, and market data through scoped paper/live controls.

Document any new MCP server with:
- purpose
- auth source
- allowed actions
- blocked actions
- log fields
- tests or smoke checks
