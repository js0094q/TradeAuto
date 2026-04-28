# Njalla VPS Deployment Runbook

Use this runbook for the single-tenant native systemd deployment path. Do not use Docker or Kubernetes for the first production deployment unless the user explicitly changes the runtime model.

## Host Provisioning

1. Create the non-root service user:

```bash
adduser trader
usermod -aG sudo trader
```

2. Harden SSH in `/etc/ssh/sshd_config`:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

3. Install base packages:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git curl unzip jq htop nginx postgresql postgresql-contrib redis-server ufw fail2ban certbot python3-certbot-nginx
```

4. Configure firewall:

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

Do not open `8000`, `5432`, `6379`, trading engine ports, admin ports, or internal metrics ports.

## Runtime Layout

```text
/opt/trading-system
  /app -> /opt/trading-system/releases/<timestamp>
  /releases
  /shared
    /.env.live
    /.env.test
    /logs
    /state
    /data
    /backups
    /config
```

Initialize the kill switch as enabled on fresh hosts:

```bash
mkdir -p /opt/trading-system/shared/state /opt/trading-system/shared/logs
echo enabled > /opt/trading-system/shared/state/kill_switch.enabled
chown -R trader:trader /opt/trading-system
```

## Validation Before Live

Run these with the real untracked live env:

```bash
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
```

Live must stay blocked until readiness passes and the protected resume path explicitly disables the kill switch.

## Service Control

```bash
systemctl status trading-api.service trading-engine-live.service telegram-bot.service
journalctl -u trading-engine-live.service -n 100 --no-pager
```

Health:

```bash
curl -fsS https://your-domain.example/health
curl -fsS -u operator:password -H "X-Admin-Token: $ADMIN_TOKEN" https://your-domain.example/ready
```

Rollback:

```bash
APP_ROOT=/opt/trading-system DOMAIN=your-domain.example ./scripts/rollback.sh
```

