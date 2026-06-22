#!/bin/bash
# Restore PostgreSQL and MinIO from a named backup.
# Run this inside the backup container or any host with pg_restore and mc.
set -euo pipefail

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; exit 1; }

usage() {
    cat <<EOF
Usage: $0 <backup-timestamp|latest>

  backup-timestamp  directory name inside /backups, e.g. 2026-06-22_12-00
  latest            use the most recent backup automatically

Required environment variables:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
EOF
    exit 1
}

[ $# -lt 1 ] && usage

BACKUP_ID="$1"

if [ "${BACKUP_ID}" = "latest" ]; then
    BACKUP_DIR=$(ls -1dt /backups/????-??-??_??-?? 2>/dev/null | head -1)
    [ -z "${BACKUP_DIR}" ] && err "No backups found in /backups"
else
    BACKUP_DIR="/backups/${BACKUP_ID}"
fi

[ -d "${BACKUP_DIR}" ] || err "Backup not found: ${BACKUP_DIR}"
[ -f "${BACKUP_DIR}/postgres.dump" ] || err "PostgreSQL dump missing: ${BACKUP_DIR}/postgres.dump"

log "Backup to restore: ${BACKUP_DIR}"
log "Target database:   ${POSTGRES_DB} on ${POSTGRES_HOST}:${POSTGRES_PORT}"

echo ""
echo "WARNING: This will DROP and REPLACE the current database '${POSTGRES_DB}'."
echo "All existing data will be permanently lost."
echo ""
read -r -p "Type RESTORE to confirm: " CONFIRM
[ "${CONFIRM}" = "RESTORE" ] || { log "Restore cancelled."; exit 0; }

# Terminate active connections so dropdb succeeds
log "Terminating active connections to ${POSTGRES_DB}..."
PGPASSWORD="${POSTGRES_PASSWORD}" psql \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
    -q

log "Dropping database ${POSTGRES_DB}..."
PGPASSWORD="${POSTGRES_PASSWORD}" dropdb \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    --if-exists "${POSTGRES_DB}"

log "Creating database ${POSTGRES_DB}..."
PGPASSWORD="${POSTGRES_PASSWORD}" createdb \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    "${POSTGRES_DB}"

log "Restoring PostgreSQL from ${BACKUP_DIR}/postgres.dump..."
PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    "${BACKUP_DIR}/postgres.dump"

log "PostgreSQL restore complete"

# MinIO restore
if [ -d "${BACKUP_DIR}/minio" ] && [ -n "$(ls -A "${BACKUP_DIR}/minio" 2>/dev/null)" ]; then
    log "Restoring MinIO buckets..."
    mc alias set local "http://${MINIO_ENDPOINT:-minio:9000}" \
        "${MINIO_ACCESS_KEY}" \
        "${MINIO_SECRET_KEY}" \
        --quiet 2>/dev/null

    for bucket_dir in "${BACKUP_DIR}/minio/"*/; do
        [ -d "${bucket_dir}" ] || continue
        bucket=$(basename "${bucket_dir}")
        log "Restoring bucket: ${bucket}"
        mc mb --ignore-existing "local/${bucket}" 2>/dev/null || true
        mc mirror --quiet "${bucket_dir}" "local/${bucket}/"
    done

    log "MinIO restore complete"
else
    log "No MinIO backup found in ${BACKUP_DIR}/minio — skipping"
fi

log "Restore complete."
log "Next steps:"
log "  1. Restart application services: docker compose -f docker-compose.prod.yml up -d"
log "  2. Verify application health"
