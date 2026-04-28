#!/usr/bin/env bash

alpaca_cli_command() {
  if [[ -n "${ALPACA_CLI_BIN:-}" ]]; then
    # shellcheck disable=SC2206
    ALPACA_CLI_COMMAND=(${ALPACA_CLI_BIN})
  elif command -v alpaca >/dev/null 2>&1; then
    ALPACA_CLI_COMMAND=(alpaca)
  elif command -v uvx >/dev/null 2>&1; then
    ALPACA_CLI_COMMAND=(uvx alpaca-cli)
  else
    echo "Alpaca CLI not found. Install alpaca or uvx alpaca-cli." >&2
    return 127
  fi
}
