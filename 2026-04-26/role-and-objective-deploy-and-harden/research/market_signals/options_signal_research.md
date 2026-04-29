# Options Signal Research

## Executive summary
Options are allowed for research as confirmation or suppression only. No options order placement was added or recommended.

## What was tested
`src/trading_system/research/signals/options.py` implements `options_liquidity_score` and `iv_rank`. Tests verify liquid options can pass as confirmation and thin/wide options are suppressed. The provider validation run also sampled 100 SPY option-chain contracts through the read-only Alpaca CLI adapter.

## Data used
Synthetic options liquidity inputs and a provider-backed SPY option-chain sample. No options order endpoint was called.

## Assumptions
Options execution is not validated. Options data can only improve or suppress equity signals until a separate options execution system is validated.

## Methodology
Options signals score volume, open interest, bid/ask spread, current IV, and IV range. Strike, expiration, earnings IV expansion, and put/call activity remain future provider-backed features.

## Results
The options signal can reject poor spread/open-interest/volume conditions and expose IV rank as an explainable confirmation feature.

## What passed
Research-only options filters are implemented and tested. The adapter can parse option-chain snapshot contracts for confirmation research.

## What failed
Strike/expiration liquidity maps, unusual volume models, put/call analysis, open-interest history, and earnings IV expansion models do not exist yet.

## Rejected strategies
All options trading strategies are rejected. Options-derived equity confirmation remains research-only until uplift tests are run.

## Strategies needing more paper/shadow validation
Options volume/open-interest confirmation for equity momentum and breakout filters.

## Any restricted live-candidate strategies, if any
None.

## Blind spot check
Options data can look predictive because of earnings, market-maker hedging, or stale quotes. Wide spreads can erase any apparent edge.

## Operational risk notes
Do not enable options trading. Keep `ALLOW_OPTIONS_TRADING=false` unless a separate approval and validation process changes policy.

## Next engineering actions
Add options-chain retrieval, point-in-time IV calculations, expiration/strike filters, and equity-signal uplift tests.
