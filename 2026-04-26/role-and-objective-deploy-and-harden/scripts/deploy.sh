#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/trading-system}"
RELEASES_DIR="${RELEASES_DIR:-${APP_ROOT}/releases}"
SHARED_DIR="${SHARED_DIR:-${APP_ROOT}/shared}"
CURRENT_LINK="${CURRENT_LINK:-${APP_ROOT}/app}"
SOURCE_DIR="${SOURCE_DIR:-$(pwd)}"
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
MODE="${MODE:-live}"
ENV_FILE="${ENV_FILE:-${SHARED_DIR}/.env.live}"
DOMAIN="${DOMAIN:-localhost}"
TIMESTAMP="$(date -u +%Y%m%d%H%M%S)"
RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"
if [[ "${MODE}" == "live" ]]; then
  SERVICES=(trading-api.service trading-engine-live.service telegram-bot.service)
else
  SERVICES=(trading-api.service trading-engine-test.service telegram-bot.service)
fi

notify_telegram() {
  local message="$1"
  if [[ -x "${RELEASE_DIR}/scripts/telegram_test.sh" && -f "${ENV_FILE}" ]]; then
    TELEGRAM_TEST_MESSAGE="${message}" "${RELEASE_DIR}/scripts/telegram_test.sh" "${ENV_FILE}" >/dev/null 2>&1 || true
  fi
}

rollback_on_failure() {
  echo "deployment failed; attempting rollback" >&2
  if [[ -x "${CURRENT_LINK}/scripts/rollback.sh" ]]; then
    "${CURRENT_LINK}/scripts/rollback.sh" || true
  fi
  notify_telegram "Trading deployment failed and rollback was attempted"
}
trap rollback_on_failure ERR

mkdir -p "${RELEASES_DIR}" "${SHARED_DIR}/logs" "${SHARED_DIR}/state" "${SHARED_DIR}/data" "${SHARED_DIR}/backups" "${SHARED_DIR}/config"
if [[ ! -f "${SHARED_DIR}/state/kill_switch.enabled" ]]; then
  echo "enabled" > "${SHARED_DIR}/state/kill_switch.enabled"
fi

if [[ -n "${REPO_URL}" ]]; then
  git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${RELEASE_DIR}"
else
  mkdir -p "${RELEASE_DIR}"
  cp -a "${SOURCE_DIR}/." "${RELEASE_DIR}/"
fi

cd "${RELEASE_DIR}"
set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m compileall src scripts tests
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/validate_env.py --env-file "${ENV_FILE}" --mode "${MODE}"

if [[ "${MODE}" == "live" ]]; then
  ./scripts/alpaca_doctor.sh live
  ./scripts/alpaca_account.sh live
  ./scripts/alpaca_clock.sh live
  ./scripts/telegram_test.sh "${ENV_FILE}"
fi

if [[ -x .venv/bin/alembic && -f alembic.ini ]]; then
  .venv/bin/alembic upgrade head
fi

ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"
sudo cp ops/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
for service in "${SERVICES[@]}"; do
  sudo systemctl restart "${service}"
done

curl -fsS "https://${DOMAIN}/health" >/dev/null
curl -fsS -H "X-Admin-Token: ${ADMIN_TOKEN:-}" "https://${DOMAIN}/ready" >/dev/null
notify_telegram "Trading deployment succeeded: ${TIMESTAMP}"
trap - ERR
echo "deployment complete: ${RELEASE_DIR}"
