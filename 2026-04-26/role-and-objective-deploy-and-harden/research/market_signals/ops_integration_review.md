# Ops Integration Review

## Executive summary
The API and Telegram surfaces are operationally useful but do not yet expose read-only research status, scorecards, shadow signals, or WebSocket health. No new order endpoints should be added.

## What was tested
FastAPI routes and Telegram command handlers were inspected.

## Data used
`src/trading_system/api/app.py`, `src/trading_system/telegram/bot.py`, `src/trading_system/health.py`, and existing tests.

## Assumptions
Any future research endpoint must be read-only and protected by existing admin-token patterns where appropriate.

## Methodology
The review listed available endpoints, missing endpoints, dashboard gaps, Telegram gaps, and recommended read-only additions.

## Results
Available API endpoints: `/health`, `/ready`, `/metrics`, `/admin/kill`, `/admin/resume`.

Available Telegram commands: `/start`, `/health`, `/status`, `/account`, `/positions`, `/orders`, `/kill`.

Recommended read-only endpoints: `/research/status`, `/research/shadow-signals`, `/research/scorecard`, `/research/latest-signals`, `/research/data-health`, `/research/websocket-health`, and `/research/risk-gates`.

## What passed
Control endpoints are protected. Telegram dangerous kill command is admin-gated.

## What failed
Dashboard and Telegram do not yet show research signal observations, scorecards, suppression reasons, or stream health.

## Rejected strategies
Any strategy requiring manual operator interpretation because observability is missing should be rejected.

## Strategies needing more paper/shadow validation
All strategies need read-only observability before restricted live-candidate review.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Adding endpoints can accidentally create control paths. Keep research routes read-only and do not expose secrets or raw account data.

## Operational risk notes
Do not add endpoints that submit, cancel, close, resume, or otherwise alter trading state.

## Next engineering actions
Add protected read-only research endpoints after the persistence format is finalized; then extend Telegram/dashboard summaries.

