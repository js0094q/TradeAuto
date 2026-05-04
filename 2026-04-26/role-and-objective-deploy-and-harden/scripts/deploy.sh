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
if [[ -z "${ENV_FILE:-}" ]]; then
  case "${MODE}" in
    live) ENV_FILE="${SHARED_DIR}/.env.live" ;;
    paper) ENV_FILE="${SHARED_DIR}/.env.paper" ;;
    *) ENV_FILE="${SHARED_DIR}/.env.test" ;;
  esac
fi
DOMAIN="${DOMAIN:-localhost}"
TIMESTAMP="$(date -u +%Y%m%d%H%M%S)"
RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"
if [[ "${MODE}" == "live" ]]; then
  SERVICES=(trading-api.service trading-engine-live.service telegram-bot.service)
  STOP_SERVICES=(trading-engine-paper.service trading-engine-test.service)
elif [[ "${MODE}" == "paper" ]]; then
  SERVICES=(trading-api.service trading-engine-paper.service telegram-bot.service)
  STOP_SERVICES=(trading-engine-live.service trading-engine-test.service)
else
  SERVICES=(trading-api.service trading-engine-test.service telegram-bot.service)
  STOP_SERVICES=(trading-engine-live.service trading-engine-paper.service)
fi

notify_telegram() {
  local message="$1"
  if [[ -x "${RELEASE_DIR}/scripts/telegram_test.sh" && -f "${ENV_FILE}" ]]; then
    TELEGRAM_TEST_MESSAGE="${message}" "${RELEASE_DIR}/scripts/telegram_test.sh" "${ENV_FILE}" >/dev/null 2>&1 || true
  fi
}

wait_for_check() {
  local name="$1"
  shift
  local attempt
  for attempt in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "deployment health check failed: ${name}" >&2
  "$@" >/dev/null
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
ln -sfn "$(basename "${ENV_FILE}")" "${SHARED_DIR}/.env.runtime"

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
for service in "${STOP_SERVICES[@]}"; do
  sudo systemctl stop "${service}" || true
  sudo systemctl disable "${service}" || true
done
for service in "${SERVICES[@]}"; do
  sudo systemctl enable "${service}"
  sudo systemctl restart "${service}"
done

wait_for_check public-health curl -fsS "https://${DOMAIN}/health"
wait_for_check local-ready curl -fsS -H "X-Admin-Token: ${ADMIN_TOKEN:-}" "http://127.0.0.1:${PORT:-8000}/ready"
notify_telegram "Trading deployment succeeded: ${TIMESTAMP}"
trap - ERR
echo "deployment complete: ${RELEASE_DIR}"
