# MCP Rules

- Do not store MCP credentials, tokens, private keys, or raw `.env` values in this folder.
- Keep tool scopes minimal and read-only by default.
- Financial, deployment, service-control, database-migration, and destructive tools must enforce approval gates.
- All tool calls that affect state must write a redacted audit event.
- Validate external tool output before feeding it into order, deployment, or policy decisions.
