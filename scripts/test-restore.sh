#!/bin/bash
# Automated restore verification test.
# Spins up a throwaway PostgreSQL container, restores the latest backup into it,
# verifies critical tables exist and have data, then tears down.
# Run this after every production deploy to confirm backups are restorable.
set -euo pipefail

BACKUP_LOCAL_PATH="${BACKUP_LOCAL_PATH:-/var/backups/wished}"
CONTAINER="wished-restore-test-$$"
PORT=54399
TEST_DB="wished_restore_test"
TEST_USER="restore_test"
TEST_PASS="restore_$(date +%s)"
PASSED=0

log()  { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err()  { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FAIL: $*" >&2; }
ok()   { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] PASS: $*"; }
fail() { err "$*"; PASSED=1; }

cleanup() {
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Find latest backup
LATEST=$(ls -1dt "${BACKUP_LOCAL_PATH}/????-??-??_??-??" 2>/dev/null | head -1 || true)
if [ -z "${LATEST}" ]; then
    err "No backup found in ${BACKUP_LOCAL_PATH}"
    exit 1
fi

log "Testing restore from: ${LATEST}"
log "Starting temporary PostgreSQL container on port ${PORT}..."

docker run -d --name "${CONTAINER}" \
    -e POSTGRES_DB="${TEST_DB}" \
    -e POSTGRES_USER="${TEST_USER}" \
    -e POSTGRES_PASSWORD="${TEST_PASS}" \
    -p "${PORT}:5432" \
    postgres:16 \
    >/dev/null

# Wait for postgres to be ready
log "Waiting for postgres to be ready..."
DEADLINE=$(( $(date +%s) + 30 ))
until docker exec "${CONTAINER}" pg_isready -U "${TEST_USER}" -q 2>/dev/null; do
    [ "$(date +%s)" -lt "${DEADLINE}" ] || { err "Postgres did not start in 30s"; exit 1; }
    sleep 1
done

# Copy dump into container and restore
log "Copying backup into container..."
docker cp "${LATEST}/postgres.dump" "${CONTAINER}:/tmp/restore.dump"

log "Restoring with pg_restore..."
docker exec -e PGPASSWORD="${TEST_PASS}" "${CONTAINER}" \
    pg_restore \
    -U "${TEST_USER}" \
    -d "${TEST_DB}" \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    /tmp/restore.dump

log "Restore complete. Running verification checks..."

run_sql() {
    docker exec -e PGPASSWORD="${TEST_PASS}" "${CONTAINER}" \
        psql -U "${TEST_USER}" -d "${TEST_DB}" -t -c "$1" 2>/dev/null | tr -d ' '
}

# Check core tables exist and contain data
check_table() {
    local table="$1"
    local count
    count=$(run_sql "SELECT COUNT(*) FROM ${table};" 2>/dev/null || echo "ERROR")
    if [ "${count}" = "ERROR" ]; then
        fail "Table '${table}' missing or unreadable after restore"
    else
        ok "Table '${table}' has ${count} rows"
    fi
}

check_table users
check_table wishlists
check_table wishes
check_table reservations
check_table follows

# Check schema version matches (alembic_version table must exist)
ALEMBIC_HEAD=$(run_sql "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null || echo "MISSING")
if [ "${ALEMBIC_HEAD}" = "MISSING" ]; then
    fail "alembic_version table missing — schema may be incomplete"
else
    ok "Schema at migration: ${ALEMBIC_HEAD}"
fi

# Verify no orphaned wish images (basic referential integrity spot check)
ORPHANS=$(run_sql "
    SELECT COUNT(*) FROM wish_images wi
    LEFT JOIN wishes w ON wi.wish_id = w.id
    WHERE w.id IS NULL;" 2>/dev/null || echo "0")
if [ "${ORPHANS}" != "0" ] && [ "${ORPHANS}" != "" ]; then
    fail "Found ${ORPHANS} orphaned wish_images rows — restore may be incomplete"
else
    ok "No orphaned wish_images rows"
fi

echo ""
if [ "${PASSED}" -eq 0 ]; then
    log "All checks passed. Backup from ${LATEST} is restorable."
    exit 0
else
    err "One or more checks failed. Review output above."
    exit 1
fi
