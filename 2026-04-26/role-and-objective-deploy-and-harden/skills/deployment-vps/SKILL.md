---
name: deployment-vps
description: Deploy or inspect the Njalla VPS using the repo scripts, systemd units, Nginx config, validation gates, rollback path, and SSH safety rules.
---

# Deployment VPS

Use this skill for VPS inspection, deploys, rollbacks, service restarts, Nginx changes, TLS checks, or host hardening.

## Safety Rules

- Do not restart services, reload Nginx, deploy code, edit remote env files, or run destructive host commands without explicit user approval for that target action.
- Do not print `.sshpw`, `.env` files, private keys, tokens, or account credentials.
- SSH access is a transport detail; production services must run as `trader`, not root.
- Nginx must remain the only public entrypoint. App services bind to `127.0.0.1`.
- Fresh hosts must initialize the kill switch as enabled before service start.

## Standard Target

- host: `45.142.140.188`
- login: `root@45.142.140.188`
- app root: `/opt/trading-system`
- active app symlink: `/opt/trading-system/app`
- shared env/state: `/opt/trading-system/shared`
- services: `trading-api.service`, `trading-engine-live.service`, `trading-engine-test.service`, `telegram-bot.service`

## Read-Only Inspection

Use read-only checks first:

```bash
ssh root@45.142.140.188 'hostname; whoami; uname -srm; systemctl is-system-running || true'
ssh root@45.142.140.188 'systemctl status trading-api.service trading-engine-live.service telegram-bot.service --no-pager'
ssh root@45.142.140.188 'ls -la /opt/trading-system /opt/trading-system/shared 2>/dev/null || true'
```

## Deploy Gate

Before a live deploy, verify locally and then on-host:

```bash
python3 -m compileall src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests
python3 scripts/validate_env.py --env-file .env.test.example --mode paper
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
```

## Rollback

Keep rollback explicit and inspectable:

```bash
APP_ROOT=/opt/trading-system DOMAIN=<domain-or-ip> ./scripts/rollback.sh
```
