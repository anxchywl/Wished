#!/usr/bin/env bash
# Start a localhost.run tunnel and wire it up to the app.
# Run this whenever the tunnel dies: scripts/tunnel.sh
set -euo pipefail

PORT=8002
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

echo "→ Starting localhost.run tunnel on port $PORT..."
ssh -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=30 \
    -o ExitOnForwardFailure=yes \
    -R "80:localhost:$PORT" nokey@localhost.run \
    > /tmp/lhr-tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait for the public URL to appear in the log
for i in $(seq 1 20); do
  URL=$(grep -o 'https://[a-z0-9-]*\.lhr\.life' /tmp/lhr-tunnel.log 2>/dev/null | tail -1)
  [[ -n "$URL" ]] && break
  sleep 1
done

if [[ -z "$URL" ]]; then
  echo "✗ Tunnel failed to start. Check /tmp/lhr-tunnel.log"
  kill "$TUNNEL_PID" 2>/dev/null
  exit 1
fi

echo "→ Tunnel URL: $URL"

# Patch .env
sed -i '' "s|TELEGRAM_MINI_APP_URL=.*|TELEGRAM_MINI_APP_URL=$URL|" "$ENV_FILE"
sed -i '' "s|ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=[\"http://127.0.0.1:3000\",\"http://localhost:3000\",\"$URL\"]|" "$ENV_FILE"
DOMAIN=$(echo "$URL" | sed 's|https://||')
sed -i '' "s|NEXT_PUBLIC_TELEGRAM_DEV_ORIGINS=.*|NEXT_PUBLIC_TELEGRAM_DEV_ORIGINS=$DOMAIN|" "$ENV_FILE"

echo "→ .env updated. Recreating bot container..."
docker compose up -d --force-recreate bot

echo "✓ Done. Open @wished_things_bot in Telegram and tap Open Wished."
echo "  Keep this terminal open — tunnel closes when you exit."

# Keep SSH alive
wait "$TUNNEL_PID"
