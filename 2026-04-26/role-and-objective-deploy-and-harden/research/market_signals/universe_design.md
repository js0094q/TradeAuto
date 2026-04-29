# Universe Design

## Executive summary
Research must be run on separated equity, ETF, options-underlying, and crypto universes. SPY, QQQ, and mega-cap tech alone are not enough.

## What was tested
Universe rules were implemented in `src/trading_system/data/universe.py` and unit-tested for spread, liquidity, options, and crypto separation.

## Data used
The current implementation uses static seed symbols plus rule-based metadata filters. Provider-backed universe refresh is a required next step.

## Assumptions
Universe membership must be reproducible from point-in-time provider data when used for backtests. Crypto must not reuse equity session assumptions.

## Methodology
Universes define inclusion, exclusion, liquidity, spread, volatility, relative-volume, exchange, asset-class, and options rules.

## Results
Core ETF universe: SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC. Minimum dollar volume: 50 million. Maximum spread: 0.25%.

Mega-cap liquid equity universe: AAPL, MSFT, NVDA, AMZN, META, GOOGL, GOOG, TSLA, AVGO, JPM, LLY, UNH, V, MA, XOM. Minimum dollar volume: 100 million. Maximum spread: 0.25%.

High-volume momentum equity universe: rule-defined from average daily volume above 2 million, dollar volume above 75 million, price above 10, spread below 0.15%, volatility between 1% and 10%, and relative volume above 1.2.

Options-capable underlying universe: requires options availability, underlying dollar volume above 100 million, spread below 0.15%, options volume above 5,000, and open interest above 20,000.

Crypto major universe: BTC/USD, ETH/USD, SOL/USD only if supported by the provider and broker. It uses 24/7 assumptions, no equity market-hours reuse, and separate weekend liquidity checks.

## What passed
The code can filter assets deterministically and keeps crypto separate.

## What failed
Point-in-time survivorship-free membership is not yet implemented.

## Rejected strategies
Any backtest using only one ticker, one ETF, or a hand-picked mega-cap subset should be rejected.

## Strategies needing more paper/shadow validation
Momentum, breakout, mean reversion, options confirmation, and crypto strategies need validation across the relevant universe rather than a single symbol.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Modern liquid symbols may not have been liquid or listed across the full 9-year window. Point-in-time constituents and delisting handling are required.

## Operational risk notes
Universe expansion can increase API load and false positives. Keep rate limits, batching, cache TTLs, and stale-data suppression active.

## Next engineering actions
Build provider-backed universe refresh, persist membership snapshots, add exchange-aware liquidity reports, and include survivorship-bias flags in backtest output.

