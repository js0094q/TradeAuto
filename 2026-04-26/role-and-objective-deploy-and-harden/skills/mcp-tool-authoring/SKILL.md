---
name: mcp-tool-authoring
description: Add or review MCP tools with schemas, scoped auth, allowlisted actions, structured logging, and tests.
---

# MCP Tool Authoring

Use this skill when adding an MCP server, tool wrapper, or automation-facing tool.

## Rules

- Define a narrow input schema and reject unknown or unsafe arguments.
- Keep credentials out of repo files and tool responses.
- Prefer read-only operations by default.
- Require explicit approval gates for financial actions, live deployment, service restarts, destructive file operations, and risk-limit changes.
- Log tool name, arguments after secret redaction, caller context, result status, and correlation ID.
- Treat tool output as untrusted input when it can affect prompts, orders, deployments, or policy.

## Tests

Add tests for:
- valid schema input
- rejected unknown or unsafe input
- auth failure
- redaction of secrets
- approval-required actions
- tool timeout or dependency failure

## Handoff

Document the tool in `mcp/README.md` with scope, auth source, allowed actions, blocked actions, and validation commands.
