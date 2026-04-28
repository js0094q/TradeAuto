# Deployment Rules

Deployment changes must be safe, inspectable, and reversible.

## Required Controls

- Nginx is the only public entrypoint.
- Application services bind to `127.0.0.1`.
- PostgreSQL and Redis bind only to localhost.
- systemd services run as `trader`.
- Env files live under `/opt/trading-system/shared` and remain untracked.
- The kill switch exists and starts enabled before any live service starts.
- TLS is configured before public live operation.
- UFW and fail2ban are enabled for production.
- Rollback path is available before deployment.

## Approval Required

- deploy to VPS
- restart or reload production services
- change Nginx routing or TLS files
- edit remote env files
- run database migrations
- change firewall rules
- wipe or rebuild host state

## Validation

Before marking deployment complete, validate:

```bash
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
curl -fsS https://<domain-or-ip>/health
curl -fsS -H "X-Admin-Token: $ADMIN_TOKEN" https://<domain-or-ip>/ready
```
