# Research Workspace

Use this folder for non-secret research artifacts:

- `strategies/`: strategy definitions, experiment notes, and candidates that are not yet part of `src/trading_system/strategy`.
- `backtests/`: backtest outputs and walk-forward results.
- `reports/`: operator-facing strategy ranking and promotion reports.

Do not store broker credentials, Telegram tokens, account exports, or raw logs here. Strategies must pass promotion gates before live use.

