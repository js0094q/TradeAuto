# Repo Inventory

## Executive summary
This repo is a live-capable Alpaca scaffold with fail-closed startup validation, a kill switch, protected FastAPI control routes, Telegram visibility, Alpaca SDK/CLI adapters, and a small strategy registry. It did not previously contain the requested market-data research infrastructure, signal library, cost-aware backtesting framework, shadow-validation recorder, rejection rules, or live-candidate scorecard. No live-trading controls were changed.

## What was tested
I inspected `src/trading_system`, `scripts`, `policies`, `tests`, and `research`. I verified that the local Alpaca CLI exists and reports version `0.0.9`. I used read-only Alpaca plugin calls for SPY, QQQ, AAPL, BTC/USD, and ETH/USD market-data samples.

## Data used
The inventory used repository source files and read-only current market-data samples. No account, order, or live trading endpoint was used.

## Assumptions
Algo Trader Plus capability is represented through Alpaca market data for this scaffold. Research code must stay separate from broker order submission and must fail closed on stale, missing, or wide-spread data.

## Methodology
The inspection looked for trading engine, strategies, indicators, data adapters, Alpaca integration, options, crypto, FastAPI endpoints, dashboard surface, Telegram commands, risk engine, live gates, env flags, tests, research folders, scripts, logs, and learning systems.

## Results
Existing runtime:
- Trading engine: `src/trading_system/trading/engine.py` validates settings before live mode and runs a supervised loop.
- Risk engine: `src/trading_system/trading/risk.py` checks kill switch, market open, tradability, limit-order requirement, market-order gate, short gate, options/crypto gates, trade count, open positions, notional limits, loss limits, spread, duplicates, cooldowns, and loss lockout.
- Strategies: `src/trading_system/strategy` has registry, base types, scoring, promotion, backtest/walk-forward stubs, and families for momentum, pullback, breakout, mean reversion, opening range, gap, ETF regime, and earnings/news avoidance.
- Alpaca integration: `src/trading_system/broker/alpaca_sdk.py` handles account, clock, positions, orders, and connectivity; `src/trading_system/broker/alpaca_cli.py` wraps CLI diagnostics; `src/trading_system/data/alpaca_market_data.py` is a read-only, injected-fetcher market-data adapter for research.
- FastAPI endpoints: `/health`, protected `/ready`, protected `/metrics`, protected `/admin/kill`, and protected `/admin/resume`.
- Telegram commands: `/start`, `/health`, `/status`, `/account`, `/positions`, `/orders`, `/kill`; admin gating applies to kill.
- Env and gates: `TRADING_MODE`, `LIVE_TRADING_ENABLED`, `ALPACA_BASE_URL`, Alpaca keys, Telegram admin IDs, risk limits, localhost host binding, kill-switch file, and health checks are validated.
- Policies: live trading rules block live market orders, short selling, options trading, crypto trading, cancel-all, close-all, service resume after material rejection, risk-limit increases, and any weakening of tokens or kill switch checks without explicit approval.
- Tests: risk engine, env validation, Telegram bot route assumptions, and strategy scoring/promotion tests existed.

## What passed
The existing scaffold has strong safety boundaries for live deployment. It already keeps strategy, broker, risk, Telegram, and API responsibilities separate.

## What failed
Before this pass, there was no dedicated research data layer, no signal dictionary, no cost/slippage/fill model, no research-grade metrics package, no hard rejection evaluator, no scorecard evaluator, and no shadow-validation recorder. Historical provider fetchers still need to be wired into the read-only adapter.

## Rejected strategies
All strategy families remain rejected for restricted live-candidate review until actual multi-year, out-of-sample, walk-forward, cost-adjusted, real-time shadow evidence exists.

## Strategies needing more paper/shadow validation
Momentum continuation, pullback in uptrend, volatility compression breakout, opening range breakout, mean reversion, ETF regime filter, gap behavior, options confirmation, and crypto trend/breakout research need paper or shadow validation.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
The largest blind spot is confusing a research scaffold with evidence. The new modules make tests and reports reproducible, but they do not prove edge without provider-backed historical jobs and shadow monitoring.

## Operational risk notes
Do not add strategy execution routes. Do not use options or crypto execution without separate validation. Keep research endpoints read-only if added later. Preserve protected control routes and kill-switch behavior.

## Next engineering actions
Wire historical Alpaca data retrieval into the new data layer, persist raw and normalized research datasets outside secret-bearing paths, run multi-regime backtests, run real-time shadow monitoring, and only then update scorecards with evidence.
