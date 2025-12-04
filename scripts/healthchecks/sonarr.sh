#!/bin/sh
# Sonarr healthcheck - verify /ping responds quickly

set -e

MAX_LATENCY_MS=${MAX_LATENCY_MS:-5000}
PING_URL=${PING_URL:-http://localhost:8989/ping}

now_ms() {
  echo $(( $(date +%s) * 1000 ))
}

START=$(now_ms)
RESPONSE=$(curl -sf --max-time 10 "$PING_URL" 2>/dev/null || true)
END=$(now_ms)

if [ -z "$RESPONSE" ]; then
  echo "Ping endpoint returned empty"
  exit 1
fi

LATENCY=$((END - START))
if [ "$LATENCY" -gt "$MAX_LATENCY_MS" ]; then
  echo "Response too slow: ${LATENCY}ms (max ${MAX_LATENCY_MS}ms)"
  exit 1
fi

echo "Healthy: latency=${LATENCY}ms"
exit 0
