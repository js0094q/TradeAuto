---
name: test-and-validate
description: Run the minimal relevant compile, unit, environment, broker, and deployment validation checks for this trading system.
---

# Test And Validate

Use this skill after code, config, risk, broker, deployment, or operator-script changes.

## Local Baseline

Run these from the repo root when Python is available:

```bash
python3 -m compileall src scripts tests
python3 -m unittest discover -s tests
python3 scripts/validate_env.py --env-file .env.test.example --mode paper
```

If a virtualenv is installed, prefer:

```bash
.venv/bin/python -m pytest
```

## Live Or VPS Checks

Only run live checks on the target host with the real untracked environment file:

```bash
python3 scripts/validate_env.py --env-file /opt/trading-system/shared/.env.live --mode live
./scripts/alpaca_doctor.sh live
./scripts/alpaca_account.sh live
./scripts/alpaca_clock.sh live
./scripts/telegram_test.sh /opt/trading-system/shared/.env.live
```

Do not claim live readiness unless those checks pass on the VPS.

## Reporting

Report:
- commands run
- pass/fail status
- any skipped checks and why
- whether validation was local, VPS, paper, test, or live
