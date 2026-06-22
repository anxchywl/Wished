#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date -u +%Y-%m-%d_%H-%M)
BACKUP_DIR="/backups/${TIMESTAMP}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "Starting backup ${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}/minio"

# PostgreSQL
log "Dumping PostgreSQL database: ${POSTGRES_DB}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --format=custom \
    --compress=9 \
    -f "${BACKUP_DIR}/postgres.dump"

DUMP_SIZE=$(du -sh "${BACKUP_DIR}/postgres.dump" | cut -f1)
log "PostgreSQL dump complete: ${DUMP_SIZE}"

# MinIO
log "Syncing MinIO buckets..."
mc alias set local "http://${MINIO_ENDPOINT:-minio:9000}" \
    "${MINIO_ACCESS_KEY}" \
    "${MINIO_SECRET_KEY}" \
    --quiet 2>/dev/null

for bucket in "${MINIO_MEDIA_BUCKET:-wished-media}" "wished-system"; do
    if mc ls "local/${bucket}" >/dev/null 2>&1; then
        log "Mirroring bucket: ${bucket}"
        mc mirror --quiet "local/${bucket}" "${BACKUP_DIR}/minio/${bucket}/"
    fi
done

log "MinIO sync complete"

# Manifest for restore verification
cat > "${BACKUP_DIR}/manifest.json" <<MANIFEST
{
  "timestamp": "${TIMESTAMP}",
  "postgres_db": "${POSTGRES_DB}",
  "minio_endpoint": "${MINIO_ENDPOINT:-minio:9000}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "format": "pg_dump custom"
}
MANIFEST

# Optional external S3 upload — backups survive complete server loss
if [ "${BACKUP_EXTERNAL_ENABLED:-false}" = "true" ]; then
    if [ -z "${BACKUP_S3_ENDPOINT:-}" ] || [ -z "${BACKUP_S3_ACCESS_KEY:-}" ] || [ -z "${BACKUP_S3_SECRET_KEY:-}" ]; then
        log "WARNING: BACKUP_EXTERNAL_ENABLED=true but S3 credentials are incomplete — skipping external upload"
    else
        log "Uploading to external storage: ${BACKUP_S3_BUCKET:-wished-backups}"
        mc alias set external "${BACKUP_S3_ENDPOINT}" \
            "${BACKUP_S3_ACCESS_KEY}" \
            "${BACKUP_S3_SECRET_KEY}" \
            --quiet 2>/dev/null
        mc mirror --quiet "${BACKUP_DIR}/" "external/${BACKUP_S3_BUCKET:-wished-backups}/${TIMESTAMP}/"
        log "External upload complete"
    fi
fi

# Retention: prune local backups older than BACKUP_RETENTION_DAYS
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
log "Enforcing ${RETENTION_DAYS}-day retention on /backups..."
find /backups -maxdepth 1 -mindepth 1 -type d \
    -name "????-??-??_??-??" \
    -mtime "+${RETENTION_DAYS}" \
    -exec rm -rf {} + 2>/dev/null || true

log "Backup complete: ${BACKUP_DIR}"

# Write a success timestamp so verify-backup and external monitors can check freshness
date -u +%Y-%m-%dT%H:%M:%SZ > /backups/.last-success
echo "${BACKUP_DIR}" >> /backups/.last-success

# Heartbeat ping — signals to external monitoring that backup succeeded.
# Set BACKUP_HEARTBEAT_URL to a healthchecks.io, BetterUptime, or UptimeRobot ping URL.
# Free setup at https://healthchecks.io — takes 2 minutes.
if [ -n "${BACKUP_HEARTBEAT_URL:-}" ]; then
    curl -fsS --retry 3 --max-time 10 "${BACKUP_HEARTBEAT_URL}" > /dev/null 2>&1 \
        && log "Heartbeat sent" \
        || log "WARNING: Heartbeat ping failed — check BACKUP_HEARTBEAT_URL"
fi
