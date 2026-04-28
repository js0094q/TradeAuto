#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/trading-system}"
RELEASES_DIR="${RELEASES_DIR:-${APP_ROOT}/releases}"
CURRENT_LINK="${CURRENT_LINK:-${APP_ROOT}/app}"
DOMAIN="${DOMAIN:-localhost}"
SERVICES=(trading-api.service trading-engine-live.service telegram-bot.service)

CURRENT_TARGET="$(readlink "${CURRENT_LINK}" || true)"
PREVIOUS_RELEASE="$(find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d | sort | grep -v "^${CURRENT_TARGET}$" | tail -n 1)"

if [[ -z "${PREVIOUS_RELEASE}" ]]; then
  echo "no previous release found" >&2
  exit 1
fi

ln -sfn "${PREVIOUS_RELEASE}" "${CURRENT_LINK}"
sudo systemctl daemon-reload
for service in "${SERVICES[@]}"; do
  sudo systemctl restart "${service}"
done

curl -fsS "https://${DOMAIN}/health" >/dev/null
if [[ -x "${CURRENT_LINK}/scripts/telegram_test.sh" ]]; then
  "${CURRENT_LINK}/scripts/telegram_test.sh" "${APP_ROOT}/shared/.env.live" >/dev/null 2>&1 || true
fi
echo "rolled back to ${PREVIOUS_RELEASE}"

