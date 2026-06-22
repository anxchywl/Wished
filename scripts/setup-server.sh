#!/bin/bash
# One-time setup on a fresh production server before first deploy.
# Run as root or with sudo.
set -euo pipefail

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; exit 1; }

BACKUP_PATH="${BACKUP_LOCAL_PATH:-/var/backups/wished}"
APP_USER="${APP_USER:-$(logname 2>/dev/null || echo "${SUDO_USER:-root}")}"

log "Setting up server for Wished production deployment"

# Docker
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "${APP_USER}"
    log "Docker installed — you may need to log out and back in for group membership"
else
    log "Docker already installed: $(docker --version)"
fi

# Backup directory — must be a host path, not a Docker volume
log "Creating backup directory: ${BACKUP_PATH}"
mkdir -p "${BACKUP_PATH}"
chmod 700 "${BACKUP_PATH}"
chown "${APP_USER}:${APP_USER}" "${BACKUP_PATH}" 2>/dev/null || true
log "Backup directory ready: ${BACKUP_PATH}"

# Verify .env exists
if [ ! -f .env ]; then
    err ".env not found. Copy .env.example and fill in all required values before deploying."
fi

# Check required production env vars are set
REQUIRED_VARS=(
    TELEGRAM_BOT_TOKEN
    JWT_SECRET_KEY
    POSTGRES_PASSWORD
    REDIS_PASSWORD
    MINIO_ACCESS_KEY
    MINIO_SECRET_KEY
    CADDY_DOMAIN
)

MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
    value=$(grep -E "^${var}=" .env | cut -d= -f2- | tr -d '"' || true)
    if [ -z "${value}" ]; then
        echo "  MISSING: ${var}"
        MISSING=1
    fi
done

if [ "${MISSING}" -eq 1 ]; then
    err "Required environment variables are not set in .env — fill them in before deploying."
fi

# Warn if external backup is not configured
EXTERNAL_ENABLED=$(grep -E "^BACKUP_EXTERNAL_ENABLED=" .env | cut -d= -f2 || echo "false")
if [ "${EXTERNAL_ENABLED}" != "true" ]; then
    echo ""
    echo "WARNING: BACKUP_EXTERNAL_ENABLED is not set to true."
    echo "Local backups only — a server failure will cause permanent data loss."
    echo "Configure BACKUP_S3_ENDPOINT, BACKUP_S3_ACCESS_KEY, BACKUP_S3_SECRET_KEY,"
    echo "and BACKUP_S3_BUCKET in .env, then set BACKUP_EXTERNAL_ENABLED=true."
    echo ""
fi

# Warn if heartbeat is not configured
HEARTBEAT=$(grep -E "^BACKUP_HEARTBEAT_URL=" .env | cut -d= -f2 || echo "")
if [ -z "${HEARTBEAT}" ]; then
    echo "WARNING: BACKUP_HEARTBEAT_URL is not set — backup failures will be silent."
    echo "Set up a free monitor at healthchecks.io or BetterUptime and paste the ping URL."
    echo ""
fi

# Install a local backup monitoring cron that logs failures to syslog.
# This works without any external service — check /var/log/syslog or journalctl for alerts.
MONITOR_SCRIPT="/usr/local/bin/check-wished-backup"
cat > "${MONITOR_SCRIPT}" <<'MONITOR'
#!/bin/bash
LAST_SUCCESS="${BACKUP_LOCAL_PATH:-/var/backups/wished}/.last-success"
MAX_AGE="${BACKUP_MAX_AGE_SECONDS:-79200}"

if [ ! -f "${LAST_SUCCESS}" ]; then
    logger -t wished-backup "ERROR: no successful backup found in ${BACKUP_LOCAL_PATH:-/var/backups/wished}"
    exit 1
fi

LAST_STR=$(head -1 "${LAST_SUCCESS}")
LAST_EPOCH=$(date -u -d "${LAST_STR}" +%s 2>/dev/null || echo 0)
AGE=$(( $(date +%s) - LAST_EPOCH ))

if [ "${AGE}" -gt "${MAX_AGE}" ]; then
    logger -t wished-backup "ERROR: last backup was ${AGE}s ago (limit ${MAX_AGE}s) — backup may have stopped"
    exit 1
fi
MONITOR
chmod +x "${MONITOR_SCRIPT}"

# Add cron job — runs every hour, logs to syslog on failure
CRON_LINE="0 * * * * ${APP_USER} ${MONITOR_SCRIPT}"
CRON_FILE="/etc/cron.d/wished-backup-monitor"
echo "${CRON_LINE}" > "${CRON_FILE}"
chmod 644 "${CRON_FILE}"
log "Backup monitor cron installed: ${CRON_FILE}"
log "Failures will appear in: journalctl -t wished-backup"

# If BACKUP_HEARTBEAT_URL is set, optionally mention healthchecks.io setup
HEARTBEAT=$(grep -E "^BACKUP_HEARTBEAT_URL=" .env 2>/dev/null | cut -d= -f2 || echo "")
if [ -z "${HEARTBEAT}" ]; then
    echo ""
    echo "TIP: For email/SMS alerts when backups fail, set BACKUP_HEARTBEAT_URL:"
    echo "  1. Go to https://healthchecks.io and create a free account"
    echo "  2. Add a check: period 6h, grace 2h"
    echo "  3. Copy the ping URL and add to .env: BACKUP_HEARTBEAT_URL=<url>"
    echo "  4. Restart: docker compose -f docker-compose.prod.yml up -d backup"
    echo ""
fi

log "Server setup complete. Run: bash scripts/deploy.sh"
