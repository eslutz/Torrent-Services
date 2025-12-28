#!/bin/sh
# Unpackerr healthcheck - verify web server/metrics endpoint responds quickly

export SERVICE_NAME=unpackerr
LOG_PATH=${LOG_PATH:-/logs/unpackerr/healthcheck.log}
mkdir -p "$(dirname "$LOG_PATH")" 2>/dev/null || true
SCRIPT_DIR="$(dirname "$0")"
. "$SCRIPT_DIR/healthcheck_utils.sh"

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-5}
METRICS_PORT=${UNPACKERR_PORT:-5656}
HEALTH_URL="http://localhost:${METRICS_PORT}/metrics"

START=$(date +%s)
HTTP_CODE=$(wget --spider --server-response --timeout=10 "$HEALTH_URL" 2>&1 | grep "^  HTTP/" | tail -1 | awk '{print $2}' || echo "000")
END=$(date +%s)

if [ "$HTTP_CODE" != "200" ]; then
  log_event "error" "Unpackerr not responding: HTTP $HTTP_CODE"
  exit 1
fi

RESPONSE_TIME=$((END - START))
if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
  log_event "error" "Unpackerr response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
  exit 1
fi

log_event "healthy" "response_time=${RESPONSE_TIME}s, http_code=$HTTP_CODE"
exit 0
