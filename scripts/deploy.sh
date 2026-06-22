#!/bin/bash
# Safe production deployment.
# NEVER runs docker compose down -v or any command that removes volumes.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

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

# Ensure the backup host directory exists before starting
BACKUP_PATH="${BACKUP_LOCAL_PATH:-/var/backups/wished}"
if [ ! -d "${BACKUP_PATH}" ]; then
    log "Creating backup directory: ${BACKUP_PATH}"
    mkdir -p "${BACKUP_PATH}"
fi

log "Deploying with ${COMPOSE_FILE} ..."

log "Pulling base images..."
docker compose -f "${COMPOSE_FILE}" pull --quiet 2>/dev/null || true

log "Building application images..."
docker compose -f "${COMPOSE_FILE}" build

log "Bringing services up (preserving all volumes)..."
# --remove-orphans cleans renamed services; -d is detached; no -v anywhere
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

log "Deployment complete."
docker compose -f "${COMPOSE_FILE}" ps
