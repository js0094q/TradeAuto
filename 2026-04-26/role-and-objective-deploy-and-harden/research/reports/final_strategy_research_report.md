# Final Strategy Research Report
## Executive Summary
This run tested five strategy families across equities and crypto using Alpaca historical bars for U.S. symbols and Binance public spot klines for crypto. The strongest raw score came from a cross-market high-beta equity filter, but the best default implementation path remains a simpler trend-following stack built around regime, trend, momentum confirmation, ATR risk, and liquidity filters. Intraday opening-range breakout was the weakest under realistic slippage and sample-size constraints.
## Core Rule Alignment
The implementation priority should use a small indicator stack where each tool answers a different question: 200 SMA for regime, 20/50 EMA for trend, RSI for momentum confirmation, ATR for risk, and relative volume plus spread for liquidity.
## Top Strategy Candidates
| Rank | Strategy | Asset Class | Score | Return Quality | Max Drawdown | Robustness | Complexity | Recommendation |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | cross_market_high_beta_confirmation_v1 | equities_etf | 91.8 | 1.06% | 0.38% | 75 | 85 | paper_validate |
| 2 | liquid_etf_mean_reversion_v1 | equities_etf | 91.7 | 0.48% | 0.22% | 75 | 79 | paper_validate |
| 3 | equity_etf_trend_regime_v1 | equities_etf | 90.6 | 3.03% | 1.10% | 75 | 88 | paper_validate |
## Best Default Starting System
- Strategy: `equity_etf_trend_regime_v1`
- Reason: it best matches the preferred structure of trend filter + momentum confirmation + ATR-based risk + liquidity filter.
- Build-first recommendation: implement this before more complex overlays even though `cross_market_high_beta_confirmation_v1` had the highest score.
## Strategy Details
### cross_market_high_beta_confirmation_v1
- Hypothesis: BTC and ETH trend confirmation can reduce weak high-beta equity entries and improve drawdown behavior during mixed risk appetite.
- Universe: QQQ, IWM, XLK, XLY, XLC
- Data: Alpaca historical stock bars; Alpaca crypto daily bars
- Timeframe: 1Day
- Entry: Select top 2 high-beta ETFs by 60d strength; Require SPY risk-on; Require BTC and ETH above 50d trend
- Exit: Exit on deselection; Exit when crypto confirmation fails; Exit when SPY regime turns off
- Risk Controls: stop=Portfolio cash switch when equity or crypto regime breaks; target=Trend hold until deselection; filter=SPY above 200d SMA plus BTC/ETH above 50d averages
- Backtest Windows: recent_short, medium_window, prior_volatile_window, sideways_window
- Results: avg return 1.06%, avg drawdown 0.38%, avg sharpe 5.57, total trades 59
- Failure Modes: Crypto filter can sideline valid equity trends; Delayed confirmation after sharp equity rebounds; Correlation breakdowns
- Why It May Work: This was the controlled improvement cycle on the ETF trend family and directly addresses the requested cross-market filter hypothesis.
- Why It May Fail: Crypto filter can sideline valid equity trends
- Implementation Notes: Paper-validate as an overlay to the existing ETF momentum framework, not as a standalone live promotion candidate.
### liquid_etf_mean_reversion_v1
- Hypothesis: Short-term oversold conditions in highly liquid ETFs can revert when the broader market regime stays constructive.
- Universe: SPY, QQQ, IWM, TLT, GLD
- Data: Alpaca historical stock bars
- Timeframe: 1Day
- Entry: Buy when z-score >= 1.5; Require benchmark regime support; Require price near or above long-term trend
- Exit: Exit on mean reversion; Exit after 5 bars; Exit on 3% stop
- Risk Controls: stop=3% from entry; target=Return to 5-day mean; filter=SPY above 200d SMA
- Backtest Windows: recent_short, medium_window, prior_volatile_window, sideways_window
- Results: avg return 0.48%, avg drawdown 0.22%, avg sharpe 16.76, total trades 46
- Failure Modes: Momentum crashes through oversold levels; Volatility regime shifts; Too many clustered signals during drawdowns
- Why It May Work: This setup is simple to explain and easy to wire, but it remains more regime-sensitive than the trend candidates.
- Why It May Fail: Momentum crashes through oversold levels
- Implementation Notes: Keep as a secondary paper-shadow module if ETF rotation needs a diversifying overlay.
### equity_etf_trend_regime_v1
- Hypothesis: Trading only the top-trending liquid ETFs during confirmed risk-on regimes should improve return quality and drawdown control.
- Universe: SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLY, XLP, TLT, GLD
- Data: Alpaca historical stock bars
- Timeframe: 1Day
- Entry: Select top 3 ETFs by 60d return; Require price above 200d SMA; Require SPY risk-on regime
- Exit: Exit on deselection; Exit when SPY regime turns risk-off
- Risk Controls: stop=Portfolio-level cash switch when SPY loses 200d trend or vol filter fails; target=Trend hold until deselection rather than fixed target; filter=SPY above 200d SMA and 20d realized vol <= 2.5%
- Backtest Windows: recent_short, medium_window, prior_volatile_window, sideways_window
- Results: avg return 3.03%, avg drawdown 1.10%, avg sharpe 1.07, total trades 127
- Failure Modes: Fast regime reversals; Late-cycle concentration in one sector; Trend lag after macro shock
- Why It May Work: The signal aligns cleanly with the existing ETF momentum and rotation architecture already present in the repo.
- Why It May Fail: Fast regime reversals
- Implementation Notes: Convert the strongest variant into a paper-only strategy class with daily rebalance logging.
## Rejected Strategies
| Strategy | Reason Rejected |
|---|---|
| crypto_momentum_volatility_expansion_v1 | failed at least half of research windows |
| opening_range_breakout_v1 | failed at least half of research windows |
## Risk Findings
- Intraday breakouts were the most sensitive to stress slippage and widened spreads.
- Mean reversion improved headline win rate but remained regime-dependent and degraded quickly during volatile windows.
- Cross-market filters helped high-beta equity exposure more than they helped crypto momentum.
- Weekend crypto exposure remained a measurable risk source even when BTC trend stayed positive.
## Implementation Plan
1. Data adapter changes
2. Strategy class/function
3. Backtest tests
4. Risk engine integration
5. Dashboard output
6. Telegram alert format
7. Paper-trading validation
8. Kill-switch validation
## Files Changed
- research/backtests/strategy_research_results.json
- research/reports/core_strategy_framework.md
- research/reports/strategy_research_log.md
- research/reports/strategy_scorecard.md
- research/reports/recommended_candidates.md
- research/reports/final_strategy_research_report.md
- research/strategies/cross_market_high_beta_confirmation_v1.yaml
- research/strategies/liquid_etf_mean_reversion_v1.yaml
- research/strategies/equity_etf_trend_regime_v1.yaml
- research/strategies/trend_following_pullback_blueprint_v1.yaml
## Verification Commands
- `python3 -m compileall src scripts tests` -> passed.
- `PYTHONPATH=src python3 -m unittest tests.data.test_binance_public_data tests.research.test_strategy_research tests.research.test_backtesting_metrics tests.research.test_scorecard` -> passed (10 tests).
- `PYTHONPATH=src python3 scripts/research/run_strategy_research.py --profile paper --feed sip` -> passed and wrote the research artifacts above.
- `python3 -m pytest ...` -> skipped because `pytest` is not installed in this environment.
- `npm test`, `npm run lint`, `npm run build` -> skipped because this repo does not expose a Node test/build surface for the research task.
## Next Research Questions
- Does a volatility-targeted position-size overlay improve the ETF rotation score without increasing operational complexity?
- Can intraday ORB quality improve with explicit spread filters from live quote snapshots rather than bar-level proxies?
- Should crypto momentum promote a weekday-only variant or a BTC-dominance regime filter before paper validation?
