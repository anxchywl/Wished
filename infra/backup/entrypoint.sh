#!/bin/bash
set -euo pipefail

INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-21600}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "Backup service started — interval: ${INTERVAL_SECONDS}s (~$(( INTERVAL_SECONDS / 3600 ))h)"
log "Running initial backup on startup..."

/usr/local/bin/backup || log "Initial backup failed — will retry in ${INTERVAL_SECONDS}s"

while true; do
    sleep "${INTERVAL_SECONDS}"
    log "Running scheduled backup..."
    /usr/local/bin/backup || log "Backup failed — will retry in ${INTERVAL_SECONDS}s"
done
