#!/bin/bash
# Safe production deployment.
# NEVER runs docker compose down -v or any command that removes volumes.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-wished}"
ENV_FILE="${ENV_FILE:-.env}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; exit 1; }

# Refuse dangerous flags even if passed explicitly
for arg in "$@"; do
    case "$arg" in
        -v|--volumes) err "Refusing --volumes flag: this destroys all database data." ;;
        --rmi)        err "Refusing --rmi flag: use 'docker image prune' separately if needed." ;;
    esac
done

[ -f "${COMPOSE_FILE}" ] || err "Compose file not found: ${COMPOSE_FILE}"

COMPOSE_ARGS=(-p "${COMPOSE_PROJECT_NAME}" -f "${COMPOSE_FILE}")
if [ -f "${ENV_FILE}" ]; then
    COMPOSE_ARGS=(--env-file "${ENV_FILE}" "${COMPOSE_ARGS[@]}")
fi

# Ensure the backup host directory exists before starting
BACKUP_PATH="${BACKUP_LOCAL_PATH:-/var/backups/wished}"
if [ ! -d "${BACKUP_PATH}" ]; then
    log "Creating backup directory: ${BACKUP_PATH}"
    mkdir -p "${BACKUP_PATH}"
fi

log "Deploying with ${COMPOSE_FILE} ..."

log "Pulling base images..."
docker compose "${COMPOSE_ARGS[@]}" pull --quiet 2>/dev/null || true

log "Building application images..."
docker compose "${COMPOSE_ARGS[@]}" build

log "Stopping app-layer services before migrations..."
# release data-network endpoints so compose can reconcile network config safely
docker compose "${COMPOSE_ARGS[@]}" stop backend bot caddy backup 2>/dev/null || true

log "Running database migrations..."
docker compose "${COMPOSE_ARGS[@]}" run --rm backend alembic upgrade head

log "Bringing services up (preserving all volumes)..."
# --remove-orphans cleans renamed services; -d is detached; no -v anywhere
docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans

log "Deployment complete."
docker compose "${COMPOSE_ARGS[@]}" ps
