# Strategy Research Rules

- Strategy code may generate signals and scores but must not submit orders.
- Do not hardcode one permanent best strategy. Use registry, scoring, and promotion gates.
- Promotion must require backtest, walk-forward, paper/test execution, risk validation, order logging validation, Telegram alert validation, and kill switch validation.
- Score strategies on out-of-sample performance, drawdown control, execution reliability, trade frequency, live readiness, risk-adjusted return, and robustness across regimes.
- Add tests when scoring, promotion, or eligibility behavior changes.

