# 2026-04-29 Dashboard + Paper Assessment

## Summary
- Dashboard auth is healthy after syncing Vercel `TRADING_API_ADMIN_TOKEN` to the active API runtime token from `/opt/trading-system/shared/.env.runtime`.
- Dashboard data plane is healthy: `/api/backend/health`, `/api/backend/ready`, `/api/backend/metrics`, and `/api/backend/paper-strategy` now return HTTP 200 through the dashboard proxy.
- The root dashboard failure was environment drift, not build failure: Vercel had an admin token that no longer matched the API service runtime token.

## What Changed Today
- Strategy research and focused candidate backtests were added and refreshed.
- Paper-mode deploy plumbing shifted API runtime env selection to `.env.runtime`.
- Dashboard added paper-cycle control and additional posture cards/metrics.
- Vercel production deploys completed successfully.

## Confirmed Root Cause
- Protected proxy calls require `X-Admin-Token`.
- API rejects the provided token (`401 unauthorized`) while health remains available.
- API service reads `/opt/trading-system/shared/.env.runtime`, while dashboard guidance still referenced `.env.live`.
- If `.env.runtime` points to `.env.paper` and Vercel token still reflects `.env.live`, dashboard appears up but cannot show protected data.

## Paper Execution Evidence (Today)
- Alpaca paper profile connectivity is healthy.
- Initial filled paper orders today were tiny, about `$1` each, which proved execution plumbing but did not provide decision-grade performance signal.
- Paper runtime was moved to a `$100,000` bankroll posture with `$25,000` max entry notional, `$30,000` position notional cap, 95% upsize threshold, and 100 bps paper limit buffer.
- Same-day upsize plumbing submitted additive paper-only orders when existing positions were below target exposure.
- Decision-grade paper positions were reached for the selected cycle: `XLE`, `XLK`, and `QQQ` each around `$25,000` market value.

## Secondary UI Issue
- Status strip now uses responsive `auto-fit` columns instead of a fixed 5-column grid.
- Dashboard now shows the actual paper execution-order rows, including target notional, current position notional, submitted order notional, quantity, and risk blocks.

## Next Session Checklist
1. Keep dashboard `TRADING_API_ADMIN_TOKEN` synced to the active backend runtime env (`/opt/trading-system/shared/.env.runtime` target) whenever the VPS runtime target changes.
2. Re-run smoke checks through dashboard proxy after each dashboard or backend deploy:
   - `/api/backend/health`
   - `/api/backend/ready`
   - `/api/backend/metrics`
   - `/api/backend/paper-strategy`
3. Preserve `.env.paper.example` as the paper evaluation sizing source of truth.
4. Treat `$1` fills as plumbing checks only; do not evaluate strategy quality from them.
5. Capture same-day runtime artifacts (`paper_strategy_status.json`, rebalance journal, order-state snapshot, and Alpaca order statuses) for stronger paper-performance attribution.
6. Keep deployment health checks retrying after systemd restarts; a single immediate public curl can falsely fail with transient `502`.
