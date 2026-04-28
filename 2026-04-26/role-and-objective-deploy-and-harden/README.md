# Trading System

Live-capable Alpaca trading system scaffold for a Njalla VPS. Production mode is restricted live trading with explicit live credentials, strict risk limits, a file-backed kill switch, Telegram operator visibility, local PostgreSQL, optional Redis, Nginx-only public exposure, and systemd supervision.

Paper mode remains available for local development, broker smoke tests, and strategy validation before promotion.

## Codex Agent Stack

This repo includes a policy-gated autonomy scaffold:

- `AGENTS.md`: repository and nested agent rules.
- `skills/`: repeatable procedures for orientation, validation, deployment, broker adapters, risk gates, MCP tools, memory, learning loops, observability, and postmortems.
- `mcp/`: MCP integration notes and security rules.
- `memory/`: generated event, decision, outcome, and reviewed lesson layout.
- `policies/`: hard rules for live trading, deployment, and destructive actions.

Learning workflows must follow: Observe -> Log -> Score -> Summarize -> Retrieve -> Propose Change -> Test -> Human/Policy Gate -> Deploy.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Njalla VPS Deployment

Target layout:

```text
/opt/trading-system
  /app -> /opt/trading-system/releases/<timestamp>
  /releases
  /shared
    /.env.test
    /.env.live
    /logs
    /data
    /backups
    /config
    /state
  /scripts
  /ops
  /research
```

Provisioning checklist:

```bash
adduser trader
usermod -aG sudo trader
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git curl unzip jq htop nginx postgresql postgresql-contrib redis-server ufw fail2ban certbot python3-certbot-nginx
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

Harden SSH in `/etc/ssh/sshd_config`:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Install ops assets:

```bash
cp ops/systemd/*.service /etc/systemd/system/
cp ops/nginx/trading-system.conf /etc/nginx/sites-available/trading-system.conf
ln -s /etc/nginx/sites-available/trading-system.conf /etc/nginx/sites-enabled/trading-system.conf
nginx -t
systemctl reload nginx
systemctl daemon-reload
```

Before starting live services, create `/opt/trading-system/shared/.env.live` from `.env.live.example` and replace every `CHANGE_ME` value. Ensure:

- `TRADING_MODE=live`
- `LIVE_TRADING_ENABLED=true`
- `ALPACA_BASE_URL=https://api.alpaca.markets`
- `HOST=127.0.0.1`
- `KILL_SWITCH_FILE=/opt/trading-system/shared/state/kill_switch.enabled`
- risk limits are present and conservative

Initialize kill switch state:

```bash
mkdir -p /opt/trading-system/shared/state /opt/trading-system/shared/logs
echo enabled > /opt/trading-system/shared/state/kill_switch.enabled
chown -R trader:trader /opt/trading-system
```

Use the protected `/admin/resume` path only after readiness validation passes. A missing kill switch file is initialized as enabled during deploy so a fresh host cannot start by silently allowing new orders.

Validate before live:

```bash
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
```

Deploy:

```bash
APP_ROOT=/opt/trading-system MODE=live ENV_FILE=/opt/trading-system/shared/.env.live DOMAIN=your-domain.example ./scripts/deploy.sh
```

Rollback:

```bash
APP_ROOT=/opt/trading-system DOMAIN=your-domain.example ./scripts/rollback.sh
```

Health surfaces:

- `/health`: process health, harmless.
- `/ready`: protected readiness; requires Nginx basic auth and `X-Admin-Token`.
- `/metrics`: localhost-only in Nginx and app-token protected.

Live acceptance gates:

- Nginx is the only public entrypoint.
- FastAPI binds to `127.0.0.1`.
- PostgreSQL and Redis are localhost-only.
- TLS is active.
- UFW and fail2ban are active.
- systemd supervises API, live engine, and Telegram bot.
- Alpaca SDK/CLI connectivity passes.
- Telegram alerts work and commands are allowlisted.
- Startup validation blocks unsafe live mode.
- Kill switch blocks trading before any live order path.
- Strategy promotion requires tests, backtest, walk-forward, paper/test execution, risk validation, order logging, Telegram alert validation, and kill switch validation.
