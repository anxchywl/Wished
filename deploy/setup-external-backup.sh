#!/bin/bash
# Interactive setup for external backup storage.
# Configures an S3-compatible bucket and validates the connection.
# Supported providers: Backblaze B2, Hetzner Object Storage, AWS S3, Cloudflare R2, any S3-compatible.
#
# After running this script, copy the printed env vars into your production .env.
set -euo pipefail

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
err() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || err "Docker is required to run this script."

echo ""
echo "External Backup Setup"
echo "====================="
echo ""
echo "Supported providers (pick one):"
echo "  1. Backblaze B2     — cheapest, \$0.006/GB/month, free egress to Cloudflare"
echo "  2. Hetzner Object   — good if app is on Hetzner, €0.0059/GB/month"
echo "  3. AWS S3           — standard option"
echo "  4. Cloudflare R2    — zero egress fees"
echo "  5. Other (any S3-compatible endpoint)"
echo ""
read -r -p "Provider (1-5): " PROVIDER_CHOICE

case "${PROVIDER_CHOICE}" in
    1)
        echo ""
        echo "Backblaze B2 setup:"
        echo "  1. Go to https://www.backblaze.com/b2/cloud-storage.html"
        echo "  2. Create an account and bucket (name: wished-backups, private)"
        echo "  3. Go to App Keys → Add Application Key"
        echo "     Bucket: wished-backups, permissions: Read and Write"
        echo "  4. Copy the keyID and applicationKey shown once"
        echo ""
        echo "  Endpoint format: https://s3.us-west-004.backblazeb2.com"
        echo "  (check your bucket details for the exact region endpoint)"
        ;;
    2)
        echo ""
        echo "Hetzner Object Storage setup:"
        echo "  1. Go to https://console.hetzner.cloud → Object Storage"
        echo "  2. Create bucket: wished-backups"
        echo "  3. Go to Security → S3 Credentials → Generate credentials"
        echo "  Endpoint: https://<region>.your-objectstorage.com"
        ;;
    3)
        echo ""
        echo "AWS S3 setup:"
        echo "  1. Create bucket in AWS console: wished-backups"
        echo "  2. Create IAM user with s3:PutObject, s3:GetObject, s3:ListBucket on the bucket"
        echo "  3. Generate access keys for the IAM user"
        echo "  Endpoint: https://s3.<region>.amazonaws.com"
        ;;
    4)
        echo ""
        echo "Cloudflare R2 setup:"
        echo "  1. Go to Cloudflare dashboard → R2 → Create bucket: wished-backups"
        echo "  2. Go to R2 → Manage R2 API tokens → Create API token (Object Read & Write)"
        echo "  Endpoint: https://<account-id>.r2.cloudflarestorage.com"
        ;;
    5)
        echo ""
        echo "Provide your S3-compatible endpoint and credentials below."
        ;;
    *)
        err "Invalid choice."
        ;;
esac

echo ""
read -r -p "S3 endpoint URL (e.g. https://s3.us-west-004.backblazeb2.com): " S3_ENDPOINT
read -r -p "Access key ID: " S3_ACCESS_KEY
read -r -s -p "Secret access key: " S3_SECRET_KEY
echo ""
read -r -p "Bucket name [wished-backups]: " S3_BUCKET
S3_BUCKET="${S3_BUCKET:-wished-backups}"

echo ""
log "Testing connection to ${S3_ENDPOINT} ..."

# Use the mc client from the backup image to test the connection
docker run --rm \
    minio/mc \
    alias set test-external "${S3_ENDPOINT}" "${S3_ACCESS_KEY}" "${S3_SECRET_KEY}" \
    >/dev/null 2>&1 || err "Failed to configure mc alias — check endpoint and credentials."

log "Testing bucket access: ${S3_BUCKET} ..."

if docker run --rm minio/mc ls "test-external/${S3_BUCKET}" >/dev/null 2>&1; then
    log "Bucket exists and is accessible."
else
    log "Bucket not found — attempting to create: ${S3_BUCKET} ..."
    docker run --rm \
        minio/mc \
        mb "test-external/${S3_BUCKET}" 2>&1 \
        || err "Could not create bucket. Create it manually in your provider's console and re-run."
    log "Bucket created: ${S3_BUCKET}"
fi

# Write a test object and read it back
TEST_FILE=$(mktemp)
echo "wished-backup-test-$(date -u +%Y%m%d%H%M%S)" > "${TEST_FILE}"
docker run --rm \
    -v "${TEST_FILE}:/tmp/test-object" \
    minio/mc \
    cp /tmp/test-object "test-external/${S3_BUCKET}/.connection-test" \
    >/dev/null 2>&1 || err "Write test failed — check bucket permissions."
rm -f "${TEST_FILE}"

docker run --rm minio/mc rm "test-external/${S3_BUCKET}/.connection-test" >/dev/null 2>&1 || true

log "Connection and write test passed."

echo ""
echo "============================="
echo "Add these lines to your .env:"
echo "============================="
echo ""
echo "BACKUP_EXTERNAL_ENABLED=true"
echo "BACKUP_S3_ENDPOINT=${S3_ENDPOINT}"
echo "BACKUP_S3_ACCESS_KEY=${S3_ACCESS_KEY}"
echo "BACKUP_S3_SECRET_KEY=<paste your secret key>"
echo "BACKUP_S3_BUCKET=${S3_BUCKET}"
echo ""
echo "Then restart the backup container:"
echo "  docker compose -f docker-compose.prod.yml up -d backup"
echo ""
log "Done. Do not commit these credentials to git."
