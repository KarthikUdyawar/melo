#!/usr/bin/env bash
# infra/monitoring.sh
# Bring up the full Melo observability stack with zero manual steps.
#
# Usage:
#   ./infra/monitoring.sh [up|down|restart|status]
#
# Requires: docker, docker compose v2
# The main Melo stack (docker-compose.yml) must already be running,
# OR pass --with-app to start it first.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MONITORING_COMPOSE="${SCRIPT_DIR}/docker-compose.monitoring.yml"
APP_COMPOSE="${ROOT_DIR}/docker-compose.yml"
ENV_FILE="${ROOT_DIR}/.env.staging"
MINIO_TOKEN_FILE="${SCRIPT_DIR}/prometheus/minio_token"

# Derive project name (matches main compose default)
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-melo}"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[monitoring] $*"; }
fail() { echo "[monitoring] ERROR: $*" >&2; exit 1; }

require_cmd() {
  command -v "$1" &>/dev/null || fail "'$1' not found in PATH"
}

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    # Export vars for docker compose interpolation (skip comments + blanks)
    set -a
    # shellcheck source=/dev/null
    source <(grep -v '^\s*#' "${ENV_FILE}" | grep -v '^\s*$')
    set +a
  else
    log "Warning: ${ENV_FILE} not found — using defaults"
  fi
}

# ── MinIO token generation ────────────────────────────────────────────────────
ensure_minio_token() {
  if [[ -f "${MINIO_TOKEN_FILE}" && -s "${MINIO_TOKEN_FILE}" ]]; then
    log "MinIO token already exists, skipping generation"
    return 0
  fi

  log "Generating MinIO metrics token..."

  # MinIO must be running in the main stack
  local minio_endpoint="${MINIO_PUBLIC_URL:-http://localhost:9000}"
  local minio_user="${MINIO_ROOT_USER:-${MINIO_ACCESS_KEY:-minioadmin}}"
  local minio_pass="${MINIO_ROOT_PASSWORD:-${MINIO_SECRET_KEY:-minioadmin}}"

  # Wait for MinIO to be healthy (up to 60s)
  local retries=12
  until docker compose \
    --project-name "${PROJECT_NAME}" \
    -f "${APP_COMPOSE}" \
    exec -T minio \
    curl -sf http://localhost:9000/minio/health/live &>/dev/null; do
    retries=$((retries - 1))
    [[ ${retries} -eq 0 ]] && fail "MinIO did not become healthy in time"
    log "Waiting for MinIO... (${retries} retries left)"
    sleep 5
  done

  # Generate token using two throwaway mc containers (entrypoint is mc itself).
  # First container sets the alias, second generates the token.
  # Parse `bearer_token: <value>` from YAML output using bash only.
  local mc_args=(
    --rm
    --network "${PROJECT_NAME}_default"
    -e "MC_HOST_local=http://${minio_user}:${minio_pass}@minio:9000"
  )

  local raw_output
  raw_output=$(docker run "${mc_args[@]}" minio/mc     admin prometheus generate local cluster     ) || fail "Failed to run mc container — is Docker running?"

  local token=""
  while IFS= read -r line; do
    case "${line}" in
      *"bearer_token:"*)
        token="${line#*bearer_token:}"
        token="${token## }"
        token="${token%% }"
        ;;
    esac
  done <<< "${raw_output}"

  if [[ -z "${token}" ]]; then
    fail "mc returned empty token — check MinIO credentials in ${ENV_FILE}"
  fi

  mkdir -p "$(dirname "${MINIO_TOKEN_FILE}")"
  echo "${token}" > "${MINIO_TOKEN_FILE}"
  log "MinIO token written to ${MINIO_TOKEN_FILE}"
}

# ── Main commands ─────────────────────────────────────────────────────────────
cmd_up() {
  local with_app=false
  [[ "${1:-}" == "--with-app" ]] && with_app=true

  require_cmd docker

  # Ensure infra config files exist
  bash "${SCRIPT_DIR}/setup-infra.sh"  # creates missing infra/ files

  load_env

  if ${with_app}; then
    log "Starting main app stack..."
    docker compose \
      --project-name "${PROJECT_NAME}" \
      -f "${APP_COMPOSE}" \
      --env-file "${ENV_FILE}" \
      up -d --force-recreate
  fi

  # Ensure main stack network + volumes exist
  local network_name="${PROJECT_NAME}_default"
  if ! docker network inspect "${network_name}" &>/dev/null; then
    fail "Network '${network_name}' not found. Start the main stack first, or use --with-app"
  fi

  # Ensure melo_logs volume exists (created by main compose)
  if ! docker volume inspect "${PROJECT_NAME}_melo_logs" &>/dev/null; then
    fail "Volume '${PROJECT_NAME}_melo_logs' not found. Start the main stack first."
  fi

  ensure_minio_token

  log "Starting monitoring stack..."
  docker compose \
    --project-name "${PROJECT_NAME}" \
    --project-directory "${SCRIPT_DIR}" \
    -f "${MONITORING_COMPOSE}" \
    --env-file "${ENV_FILE}" \
    up -d --force-recreate

  log ""
  log "Monitoring stack is up:"
  log "  Grafana      → http://localhost:3001  (admin / \${GRAFANA_ADMIN_PASSWORD:-admin})"
  log "  Prometheus   → http://localhost:9090"
  log "  Loki         → http://localhost:3100"
  log "  Tempo        → http://localhost:3200"
  log "  Pyroscope    → http://localhost:4040"
  log "  Flower       → http://localhost:5555"
  log "  cAdvisor     → http://localhost:8090"
  log "  Node Exporter→ http://localhost:9100"
}

cmd_down() {
  load_env
  log "Stopping monitoring stack..."
  docker compose \
    --project-name "${PROJECT_NAME}" \
    --project-directory "${SCRIPT_DIR}" \
    -f "${MONITORING_COMPOSE}" \
    --env-file "${ENV_FILE}" \
    down
}

cmd_restart() {
  cmd_down
  cmd_up "${@}"
}

cmd_status() {
  load_env
  docker compose \
    --project-name "${PROJECT_NAME}" \
    --project-directory "${SCRIPT_DIR}" \
    -f "${MONITORING_COMPOSE}" \
    --env-file "${ENV_FILE}" \
    ps
}

# ── Entrypoint ────────────────────────────────────────────────────────────────
COMMAND="${1:-up}"
shift || true

case "${COMMAND}" in
  up)      cmd_up "${@}" ;;
  down)    cmd_down ;;
  restart) cmd_restart "${@}" ;;
  status)  cmd_status ;;
  *)
    echo "Usage: $0 [up [--with-app] | down | restart [--with-app] | status]"
    exit 1
    ;;
esac
