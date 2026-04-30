#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-https://www.jlsprojects.com}"
ENV_FILE="${ENV_FILE:-apps/dashboard/.env.local}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${DASHBOARD_ACCESS_TOKEN:-}" ]]; then
  echo "DASHBOARD_ACCESS_TOKEN is required in env or ${ENV_FILE}" >&2
  exit 2
fi

COOKIE_JAR="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

login_status="$(
  curl -sS -o /dev/null -w "%{http_code}" \
    -c "${COOKIE_JAR}" \
    -H "Content-Type: application/json" \
    -X POST "${DASHBOARD_URL%/}/api/session" \
    --data "{\"token\":\"${DASHBOARD_ACCESS_TOKEN}\"}"
)"

if [[ "${login_status}" != "200" ]]; then
  echo "dashboard login failed: HTTP ${login_status}" >&2
  exit 1
fi

for path in health ready metrics paper-strategy live-strategy; do
  body_file="$(mktemp)"
  status="$(
    curl -sS -o "${body_file}" -w "%{http_code}" \
      -b "${COOKIE_JAR}" \
      "${DASHBOARD_URL%/}/api/backend/${path}"
  )"
  if [[ "${status}" == "401" ]]; then
    rm -f "${body_file}"
    echo "/api/backend/${path}: HTTP 401 (admin token drift)" >&2
    exit 1
  fi
  if grep -q "TRADING_API_ADMIN_TOKEN is not configured" "${body_file}"; then
    rm -f "${body_file}"
    echo "/api/backend/${path}: dashboard admin token is not configured" >&2
    exit 1
  fi
  if [[ "${path}" == "ready" && "${status}" == "503" ]]; then
    rm -f "${body_file}"
    echo "/api/backend/${path}: HTTP ${status} (readiness blocked, auth path reached)"
    continue
  fi
  rm -f "${body_file}"
  if [[ "${status}" -lt 200 || "${status}" -ge 300 ]]; then
    echo "/api/backend/${path}: HTTP ${status}" >&2
    exit 1
  fi
  echo "/api/backend/${path}: HTTP ${status}"
done
