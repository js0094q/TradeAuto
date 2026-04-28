# Script Rules

- Scripts must be shell-safe: `set -euo pipefail` unless there is a specific reason not to.
- Dangerous broker actions must require explicit confirmation such as `REQUIRE_CONFIRMATION=YES_I_UNDERSTAND`.
- Scripts may read untracked env files but must not print secrets.
- Deployment scripts must verify health/readiness and roll back on failure.
- Prefer configurable paths with safe defaults under `/opt/trading-system`.

