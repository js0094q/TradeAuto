# Trading Execution Rules

- This folder owns order safety, engine startup, risk checks, and kill switch behavior.
- Every new order path must call the risk engine before broker submission.
- Default to limit orders. Market orders require explicit config and tests.
- Live mode must not fall back to paper mode.
- Keep paper/test code useful for smoke tests only; do not make paper the production default.
- Dangerous operations such as cancel-all, close-all, `/resume`, and live trading enablement must remain explicitly gated and auditable.

