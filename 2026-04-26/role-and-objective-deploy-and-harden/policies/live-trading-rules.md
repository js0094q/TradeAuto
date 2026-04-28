# Live Trading Rules

Live trading is blocked unless every required control passes.

## Required Controls

- `TRADING_MODE=live`
- `LIVE_TRADING_ENABLED=true`
- `ALPACA_BASE_URL=https://api.alpaca.markets`
- real live Alpaca credentials in an untracked env source
- `HOST=127.0.0.1`
- readable kill switch file
- kill switch initialized as enabled on fresh hosts
- required risk limits present and positive
- limit orders required unless the user explicitly changes policy
- protected `/ready`, `/admin/kill`, `/admin/resume`, and `/metrics`
- Telegram admin chat IDs configured for dangerous commands
- order logging and audit logging enabled
- VPS validation passes with the live env

## Blocked Without Explicit Approval

- live market orders
- short selling
- options trading
- crypto trading
- cancel-all
- close-all
- service resume after material risk rejection
- risk-limit increases
- weakening endpoint, token, kill switch, or approval checks

The agent may propose changes to this file, but it may not treat proposed changes as active policy until reviewed and approved.
