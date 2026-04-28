# Trading System Dashboard

Next.js dashboard deployable to Vercel for monitoring the VPS-backed trading system at `https://jlsprojects.com`.

## Security Model

- The browser calls only this Vercel app.
- Vercel route handlers call the VPS with `TRADING_API_ADMIN_TOKEN`.
- Backend paths are allowlisted in `app/api/backend/[...path]/route.ts`.
- Control actions are disabled unless `DASHBOARD_ALLOW_CONTROL_ACTIONS=true`.
- Resume trading additionally requires the confirmation phrase `YES_I_UNDERSTAND`.

## Vercel Project Settings

Set the Vercel project root to:

```text
apps/dashboard
```

Required environment variables:

```text
TRADING_API_BASE_URL=https://jlsprojects.com
TRADING_API_ADMIN_TOKEN=<value from /opt/trading-system/shared/.env.live ADMIN_TOKEN>
TRADING_API_BASIC_AUTH=<operator>:<value from /opt/trading-system/shared/config/nginx_operator_password>
DASHBOARD_ACCESS_TOKEN=<operator login token>
DASHBOARD_SESSION_SECRET=<random cookie secret>
DASHBOARD_ALLOW_CONTROL_ACTIONS=false
```

Keep `DASHBOARD_ALLOW_CONTROL_ACTIONS=false` for monitoring-only mode. Set it to `true` only when operator control actions are explicitly approved.

## Local Development

```bash
cp .env.example .env.local
npm ci
npm run typecheck
npm run build
npm run dev
```

Open `http://localhost:3000` and sign in with `DASHBOARD_ACCESS_TOKEN`.
