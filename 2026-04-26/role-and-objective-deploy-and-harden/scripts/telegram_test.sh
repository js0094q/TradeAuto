#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-}"
if [[ -n "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_ALLOWED_CHAT_IDS:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS are required" >&2
  exit 1
fi

CHAT_ID="${TELEGRAM_TEST_CHAT_ID:-${TELEGRAM_ALLOWED_CHAT_IDS%%,*}}"
MESSAGE="${TELEGRAM_TEST_MESSAGE:-Trading system Telegram test passed}"
curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":\"${CHAT_ID}\",\"text\":\"${MESSAGE}\"}" >/dev/null

echo "telegram test message sent"
