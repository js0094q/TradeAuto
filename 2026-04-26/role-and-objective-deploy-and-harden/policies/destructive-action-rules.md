# Destructive Action Rules

Destructive actions require explicit user approval and a rollback or backup plan when practical.

## Destructive Actions

- deleting files, releases, logs, state, databases, backups, or env files
- `rm`, `truncate`, forced overwrites, or recursive moves
- `git reset --hard`, forced checkout, branch deletion, or history rewrite
- service disablement or removal
- firewall rule removal
- database migrations that drop or rewrite data
- broker actions that cancel, close, liquidate, or submit live orders

## Required Before Action

- target path, service, database, or broker scope
- reason for action
- backup or rollback path
- expected blast radius
- explicit approval from the user

## After Action

Record a redacted audit event with timestamp, actor, command category, target, result, and validation command.
