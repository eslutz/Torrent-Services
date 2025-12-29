#!/bin/sh
# Apprise healthcheck - verify service health with API check
# 
# Validates that Apprise API is responding and healthy

export SERVICE_NAME=apprise
LOG_PATH=${LOG_PATH:-/logs/apprise/healthcheck.log}
mkdir -p "$(dirname "$LOG_PATH")" 2>/dev/null || true
SCRIPT_DIR="$(dirname "$0")"
. "$SCRIPT_DIR/healthcheck_utils.sh"

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-5}

# Check API health endpoint
HEALTH_URL="http://localhost:8000/health"

START=$(date +%s)
RESPONSE=$(wget -qO- --timeout=10 "$HEALTH_URL" 2>/dev/null || echo "")
END=$(date +%s)

if [ -z "$RESPONSE" ]; then
  log_event "error" "Apprise API not responding"
  exit 1
fi

# Check for error in response
if echo "$RESPONSE" | grep -qi "error\|fail"; then
  log_event "error" "Apprise health check failed: $RESPONSE"
  exit 1
fi

RESPONSE_TIME=$((END - START))
if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
  log_event "error" "Apprise API response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
  exit 1
fi

log_event "healthy" "response_time=${RESPONSE_TIME}s"
exit 0
