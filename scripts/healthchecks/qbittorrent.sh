#!/bin/sh
# qBittorrent healthcheck - ensure API responds quickly with a version string

set -e

MAX_LATENCY_MS=${MAX_LATENCY_MS:-5000}
API_URL=${API_URL:-http://localhost:8080/api/v2/app/version}

now_ms() {
  echo $(( $(date +%s) * 1000 ))
}

START=$(now_ms)
RESPONSE=$(curl -sf --max-time 10 "$API_URL" 2>/dev/null || true)
END=$(now_ms)

if [ -z "$RESPONSE" ]; then
  echo "API returned empty response"
  exit 1
fi

LATENCY=$((END - START))
if [ "$LATENCY" -gt "$MAX_LATENCY_MS" ]; then
  echo "API response too slow: ${LATENCY}ms (max ${MAX_LATENCY_MS}ms)"
  exit 1
fi

echo "Healthy: version=${RESPONSE}, latency=${LATENCY}ms"
exit 0
