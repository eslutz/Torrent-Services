#!/bin/sh
# Tor proxy healthcheck - verify SOCKS port and Tor circuit

set -e

SOCKS_HOST=${SOCKS_HOST:-localhost}
SOCKS_PORT=${SOCKS_PORT:-9050}
TOR_CHECK_URL=${TOR_CHECK_URL:-https://check.torproject.org/api/ip}

if ! nc -z -w 5 "$SOCKS_HOST" "$SOCKS_PORT" >/dev/null 2>&1; then
  echo "SOCKS port ${SOCKS_PORT} not listening"
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  RESULT=$(curl -sf --max-time 15 --socks5-hostname "${SOCKS_HOST}:${SOCKS_PORT}" "$TOR_CHECK_URL" 2>/dev/null || true)
  if [ -z "$RESULT" ]; then
    echo "Tor circuit check failed"
    exit 1
  fi

  if echo "$RESULT" | grep -q '"IsTor":true'; then
    echo "Healthy: Tor circuit verified"
    exit 0
  else
    echo "Tor circuit response invalid"
    exit 1
  fi
fi

echo "Healthy: SOCKS port available"
exit 0
