#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-${ALPACA_CLI_PROFILE:-paper}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/alpaca_cli.sh
source "${SCRIPT_DIR}/lib/alpaca_cli.sh"
alpaca_cli_command

if ALPACA_PROFILE="${PROFILE}" "${ALPACA_CLI_COMMAND[@]}" --profile "${PROFILE}" --quiet position list; then
  exit 0
fi

# Backward-compatibility fallback for older CLI shapes.
ALPACA_PROFILE="${PROFILE}" "${ALPACA_CLI_COMMAND[@]}" --profile "${PROFILE}" --quiet positions list
