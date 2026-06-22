#!/bin/bash
# Verify the most recent backup is structurally valid.
# Exits non-zero if verification fails (use in monitoring/alerting).
set -euo pipefail

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; exit 1; }

LATEST=$(ls -1dt /backups/????-??-??_??-?? 2>/dev/null | head -1)
[ -n "${LATEST}" ] || err "No backups found in /backups"

log "Verifying backup: ${LATEST}"

# PostgreSQL dump must exist and be non-empty
[ -f "${LATEST}/postgres.dump" ] || err "PostgreSQL dump missing: ${LATEST}/postgres.dump"

DUMP_SIZE_BYTES=$(wc -c < "${LATEST}/postgres.dump")
[ "${DUMP_SIZE_BYTES}" -gt 0 ] || err "PostgreSQL dump is empty"

# pg_restore --list reads the dump TOC without restoring — catches corrupt files
pg_restore --list "${LATEST}/postgres.dump" > /dev/null 2>&1 \
    || err "PostgreSQL dump is corrupt or unreadable: ${LATEST}/postgres.dump"

DUMP_SIZE=$(du -sh "${LATEST}/postgres.dump" | cut -f1)
log "PostgreSQL dump OK: ${DUMP_SIZE}"

TABLE_COUNT=$(pg_restore --list "${LATEST}/postgres.dump" | grep -c "TABLE DATA" || true)
log "Tables in backup: ${TABLE_COUNT}"
pg_restore --list "${LATEST}/postgres.dump" \
    | grep "TABLE DATA" \
    | awk '{print "  -", $(NF-1)}' \
    | sort

# Manifest check
[ -f "${LATEST}/manifest.json" ] || log "WARNING: manifest.json missing"

# Age check via .last-success timestamp written by backup.sh
MAX_AGE="${BACKUP_MAX_AGE_SECONDS:-79200}"  # 22h default: covers 6h interval + buffer

if [ -f /backups/.last-success ]; then
    LAST_SUCCESS_STR=$(head -1 /backups/.last-success)
    LAST_SUCCESS_EPOCH=$(date -u -d "${LAST_SUCCESS_STR}" +%s 2>/dev/null \
        || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "${LAST_SUCCESS_STR}" +%s 2>/dev/null \
        || echo 0)
    NOW=$(date +%s)
    AGE_SECONDS=$(( NOW - LAST_SUCCESS_EPOCH ))

    if [ "${AGE_SECONDS}" -gt "${MAX_AGE}" ]; then
        err "Last successful backup was ${AGE_SECONDS}s ago (max ${MAX_AGE}s) — backup may have stopped"
    fi
    log "Last successful backup: ${LAST_SUCCESS_STR} (${AGE_SECONDS}s ago)"
else
    log "WARNING: .last-success not found — backup has not completed yet or is pre-update"
fi

log "Verification passed: ${LATEST}"
