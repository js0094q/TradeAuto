# Trading System Dashboard

Next.js dashboard deployable to Vercel for monitoring the VPS-backed trading system at `https://www.jlsprojects.com`.

## Security Model

- The browser calls only this Vercel app.
- Vercel route handlers call the VPS with `TRADING_API_ADMIN_TOKEN`.
- Backend paths are allowlisted in `app/api/backend/[...path]/route.ts`.
- Control actions are disabled unless `DASHBOARD_ALLOW_CONTROL_ACTIONS=true`.
- Resume trading additionally requires the confirmation phrase `YES_I_UNDERSTAND`.

## Vercel Project Settings

Set the Vercel project root to:

```text
2026-04-26/role-and-objective-deploy-and-harden/apps/dashboard
```

Required environment variables:

```text
TRADING_API_BASE_URL=https://45.142.140.188.sslip.io
TRADING_API_HOST_HEADER=45.142.140.188.sslip.io
TRADING_API_TLS_SERVERNAME=45.142.140.188.sslip.io
TRADING_API_ADMIN_TOKEN=<value from /opt/trading-system/shared/.env.live ADMIN_TOKEN>
TRADING_API_BASIC_AUTH=<operator>:<value from /opt/trading-system/shared/config/nginx_operator_password>
DASHBOARD_ACCESS_TOKEN=<operator login token>
DASHBOARD_SESSION_SECRET=<random cookie secret>
DASHBOARD_ALLOW_CONTROL_ACTIONS=false
```

Keep `DASHBOARD_ALLOW_CONTROL_ACTIONS=false` for monitoring-only mode. Set it to `true` only when operator control actions are explicitly approved.

Because DNS for `jlsprojects.com` is currently pointed at Vercel while the API remains on the VPS, production uses the VPS-specific hostname:

```text
TRADING_API_BASE_URL=https://45.142.140.188.sslip.io
TRADING_API_HOST_HEADER=45.142.140.188.sslip.io
TRADING_API_TLS_SERVERNAME=45.142.140.188.sslip.io
```

This keeps the browser proxy-only while the server route connects to the VPS through a renewable Let’s Encrypt certificate.

The Vercel app also exposes public `/health`, which proxies the VPS health endpoint for uptime checks. Protected backend routes still require a dashboard session plus the server-side backend credentials.

## Local Development

```bash
cp .env.example .env.local
npm ci
npm run typecheck
npm run build
npm run dev
```

Open `http://localhost:3000` and sign in with `DASHBOARD_ACCESS_TOKEN`.
