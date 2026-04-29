# Dashboard Rules

- This app is deployable to Vercel from `apps/dashboard`.
- Browser code must never call the VPS, Alpaca, or Telegram directly.
- Server-side route handlers are the only place `TRADING_API_ADMIN_TOKEN` may be used.
- Keep backend paths allowlisted. Do not add wildcard proxy behavior.
- Default to read-only monitoring. Control actions require `DASHBOARD_ALLOW_CONTROL_ACTIONS=true` and explicit confirmation phrases.
- Do not store operator tokens in local storage or client-visible environment variables.
- Production `TRADING_API_BASE_URL` must be HTTPS. If `jlsprojects.com` DNS points at Vercel, use the VPS-specific HTTPS hostname and keep browser traffic proxy-only through Vercel routes.
