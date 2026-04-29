# Core Strategy Framework
## Core Rule
Use a small set of indicators that answer different questions instead of stacking many overlapping signals.
## Default Indicator Stack
| Function | Indicator | Role |
|---|---|---|
| Regime | 200 SMA | Long-only or no-trade bias |
| Trend | 20 EMA and 50 EMA | Pullback direction and trend quality |
| Momentum confirmation | RSI | Require RSI to hold above 40 in long pullbacks |
| Volatility and stops | ATR | Position sizing and 2x ATR stop framework |
| Execution and liquidity | Relative volume and spread | Avoid low-participation or wide-spread trades |
## Implementation Principle
Technical indicators are tools, not standalone signals. Each approved candidate should answer regime, trend, momentum, volatility, liquidity, and risk with the smallest practical stack.
## Best Default Starting System
- Strategy: `equity_etf_trend_regime_v1`
- Why: it best matches the trend filter + momentum confirmation + ATR risk + liquidity filter structure.
- Current research status: `paper_validate` with score 90.6.
- Suggested refinement before implementation: add explicit 20/50 EMA pullback entry, RSI>40 confirmation, ATR sizing, and a relative-volume guard.
## Avoid As Primary Signals
- RSI alone
- MACD alone
- Bollinger Bands alone
- Candlestick patterns without trend and volume context
- News or sentiment as standalone triggers
