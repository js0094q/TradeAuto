# Project Overview

This repository is a live-capable Alpaca trading platform scaffold for deployment on a single-tenant Njalla VPS. The production target is restricted live trading with Alpaca, Telegram operator visibility, Nginx-fronted HTTPS, localhost-bound application services, systemd supervision, persistent logs, fail-closed startup validation, and a strategy research layer.

Main runtime pieces:
- `src/trading_system/api`: FastAPI health, readiness, metrics, and protected control routes.
- `src/trading_system/trading`: live/test engine entrypoints, risk checks, order safety rules, and kill switch behavior.
- `src/trading_system/broker`: Alpaca SDK and Alpaca CLI diagnostic adapters.
- `src/trading_system/telegram`: Telegram command handling and alerts.
- `src/trading_system/strategy`: strategy registry, scoring, backtest, walk-forward, and promotion framework.
- `ops`: Nginx and systemd deployment assets for `/opt/trading-system`.
- `scripts`: deployment, rollback, validation, Alpaca CLI, and Telegram diagnostic scripts.

Expected runtime is native Python 3.11+ on Ubuntu/Njalla VPS with systemd, Nginx, UFW, fail2ban, local PostgreSQL, optional local Redis, and Python virtualenv. Do not introduce Kubernetes. Docker Compose can be discussed later but is not the primary deployment path.

# Repository Structure

- `src/trading_system/`: Python package for API, broker, trading, Telegram, health, config, and strategy code.
- `tests/`: unit tests for safety-critical validation, risk, and strategy scoring behavior.
- `scripts/`: operator scripts. Dangerous scripts must require explicit confirmation.
- `ops/nginx/`: Nginx site config. Nginx is the only public entrypoint.
- `ops/systemd/`: service units for API, live engine, test engine, and Telegram bot.
- `ops/deploy/`: optional deployment support files.
- `docs/`: operator runbooks and deployment notes.
- `research/strategies`, `research/backtests`, `research/reports`: generated research artifacts and reports.
- `skills/`: repo-local Codex skills for repeatable agent procedures.
- `mcp/`: MCP integration notes, scopes, and security rules.
- `memory/`: generated agent memory layout for events, decisions, outcomes, and reviewed lessons.
- `policies/`: hard autonomy, deployment, destructive-action, and live-trading rules.

Nested `AGENTS.md` files may tighten rules for trading execution, strategy research, scripts, and ops.

# Development Setup

Use a local virtualenv:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Environment files:
- `.env.test.example` is for paper/test smoke validation only.
- `.env.live.example` is for restricted live production configuration.
- Real `.env`, `.env.test`, `.env.live`, and secret-bearing files must remain untracked.

Live mode must use live Alpaca credentials and `ALPACA_BASE_URL=https://api.alpaca.markets`. Paper mode must use the paper endpoint and must not be represented as live.

# Build Commands

There is no compiled frontend or package build yet. Validate Python syntax with:

```bash
python3 -m compileall src scripts tests
```

If dependencies are installed, run:

```bash
.venv/bin/python -m pytest
```

# Test and Validation Commands

Primary local checks:

```bash
python3 -m compileall src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests
python3 scripts/validate_env.py --env-file .env.test.example --mode paper
```

`.env.live.example` is a template and should fail validation until copied to an untracked live env with real secrets and an initialized kill switch file.

Before live deployment, run from the VPS with the real untracked live env:

```bash
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
```

Fix test, lint, type, validation, and startup errors before marking work complete. Do not claim live readiness without command evidence from the actual target environment.

# Coding Conventions

- Keep changes small, direct, and reversible.
- Use existing modules before adding new architecture.
- Keep broker, risk, strategy, and transport boundaries separate.
- Do not let strategy code submit orders directly. Orders must pass through risk and execution boundaries.
- Use dataclasses or typed objects for structured trading decisions, risk decisions, and strategy metrics.
- Fail closed for missing config, ambiguous live flags, paper/live endpoint crossover, missing risk limits, unreadable kill switch state, and unavailable logging.
- Add tests for changed risk, validation, strategy promotion, Telegram authorization, or order behavior.

# Security and Safety Rules

- Never commit secrets, API keys, tokens, credentials, `.env` files, build artifacts, cache directories, virtualenvs, or generated dependency folders.
- Never commit `.sshpw`, private keys, raw MCP credentials, raw memory logs containing secrets, or secret-bearing tool output.
- Nginx must be the only public entrypoint. FastAPI must bind to `127.0.0.1`.
- PostgreSQL and Redis must bind only to localhost.
- Preserve paper/live trading boundaries unless the user explicitly changes them.
- Treat financial execution code as high-risk.
- Live orders require explicit live flags, live Alpaca endpoint, risk limits, readable kill switch state, logging, and startup validation.
- Market orders, short selling, options, crypto, cancel-all, close-all, and resume behavior must remain explicitly gated.
- Telegram commands must be allowlisted by chat ID. Dangerous commands require admin chat ID.
- Avoid destructive commands unless explicitly requested.

# Deployment Notes

Deployment target is `/opt/trading-system`:

- `/opt/trading-system/app` symlinks to the active release.
- `/opt/trading-system/releases` stores timestamped releases.
- `/opt/trading-system/shared` stores untracked env files, logs, state, data, config, and backups.
- `ops/systemd/*.service` are copied to `/etc/systemd/system/`.
- `ops/nginx/trading-system.conf` is copied to `/etc/nginx/sites-available/`.

Post-deploy validation should check `/health`, protected `/ready`, systemd service status, Alpaca SDK/CLI connectivity, Telegram alert delivery, kill switch behavior, and Nginx/TLS exposure.

# Pull Request / Commit Guidance

- Prefer focused commits with a short imperative subject.
- Include changed files, validation commands run, and remaining risks in the handoff.
- Do not commit generated research outputs unless the user asks for those artifacts to be versioned.
- Do not commit local service logs, local state, database files, credentials, or deployment secrets.

# Agent Workflow Rules

- Read the nearest `AGENTS.md` before editing files.
- Closest nested `AGENTS.md` overrides root instructions.
- Explicit user chat instructions override `AGENTS.md`.
- Use `skills/` for repeatable repo procedures when a task matches an available skill.
- Treat `policies/` as hard gates. Agent memory and learning outputs may propose changes but may not bypass policy.
- Inspect relevant files before editing.
- Do not make broad refactors unless requested.
- Add or update tests for changed behavior.
- After moving files or changing imports, run relevant compile/test commands.
- For risky trading, infrastructure, or credential changes, choose conservative fail-closed behavior and report any controls weakened by the requested change.
