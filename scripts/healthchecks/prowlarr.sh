#!/bin/sh
# Prowlarr healthcheck - verify API health endpoint

set -e

MAX_LATENCY_MS=${MAX_LATENCY_MS:-5000}

# Use /health endpoint if API key is available, otherwise fall back to /ping
if [ -n "$PROWLARR_API_KEY" ]; then
  HEALTH_URL="http://localhost:9696/api/v1/health"
  HEADER="X-Api-Key: $PROWLARR_API_KEY"
else
  HEALTH_URL="http://localhost:9696/ping"
  HEADER=""
fi

now_ms() {
  echo $(( $(date +%s) * 1000 ))
}

START=$(now_ms)
if [ -n "$HEADER" ]; then
  RESPONSE=$(curl -sf --max-time 10 -H "$HEADER" "$HEALTH_URL" 2>/dev/null || true)
else
  RESPONSE=$(curl -sf --max-time 10 "$HEALTH_URL" 2>/dev/null || true)
fi
END=$(now_ms)

if [ -z "$RESPONSE" ]; then
  echo "Health endpoint returned empty"
  exit 1
fi

# If using /health endpoint, check for any warnings or errors
if [ -n "$PROWLARR_API_KEY" ]; then
  if echo "$RESPONSE" | grep -qi '"type":"error"\|"type":"warning"'; then
    echo "Health check failed: service reported issues"
    exit 1
  fi
fi

LATENCY=$((END - START))
if [ "$LATENCY" -gt "$MAX_LATENCY_MS" ]; then
  echo "Response too slow: ${LATENCY}ms (max ${MAX_LATENCY_MS}ms)"
  exit 1
fi

echo "Healthy: latency=${LATENCY}ms"
exit 0
