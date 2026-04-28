# Trading System Code Rules

- Keep `config`, `health`, `risk`, `kill_switch`, `broker`, `trading`, `telegram`, and `strategy` responsibilities separate.
- Do not perform broker network calls at import time.
- Do not submit orders from API, Telegram, or strategy modules directly; route through the trading/risk boundary.
- Live mode must fail closed on ambiguous flags, missing risk limits, missing Telegram admin IDs, unreadable kill switch state, paper endpoints, unavailable logging, or unsafe host binding.
- Use typed dataclasses for decisions and compact result objects so tests can assert exact failure reasons.
- Add unit tests for any changed safety behavior.

