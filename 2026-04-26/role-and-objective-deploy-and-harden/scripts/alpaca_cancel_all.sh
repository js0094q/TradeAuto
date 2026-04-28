#!/usr/bin/env bash
set -euo pipefail

if [[ "${REQUIRE_CONFIRMATION:-}" != "YES_I_UNDERSTAND" ]]; then
  echo "Refusing to cancel orders without REQUIRE_CONFIRMATION=YES_I_UNDERSTAND" >&2
  exit 2
fi

PROFILE="${1:-${ALPACA_CLI_PROFILE:-paper}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/alpaca_cli.sh
source "${SCRIPT_DIR}/lib/alpaca_cli.sh"
alpaca_cli_command

"${ALPACA_CLI_COMMAND[@]}" orders cancel --all --profile "${PROFILE}"
