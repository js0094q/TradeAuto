# Ops Rules

- Nginx is the only public entrypoint. Application services bind to `127.0.0.1`.
- PostgreSQL and Redis must not be publicly exposed.
- Systemd services must run as the non-root `trader` user.
- Do not put real secrets in ops files.
- Keep live and test services on separate environment files.
- Maintain rollback paths for deployment changes.
- Do not reload or restart production services from Codex without an explicit target host and user approval.

