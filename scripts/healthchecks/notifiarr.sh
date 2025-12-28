#!/bin/sh
# Notifiarr healthcheck - verify service health with API check
# 
# Validates that Notifiarr is responding and healthy
# Requires DN_API_KEY to be set for authenticated checks

export SERVICE_NAME=notifiarr
LOG_PATH=${LOG_PATH:-/logs/notifiarr/healthcheck.log}
mkdir -p "$(dirname "$LOG_PATH")" 2>/dev/null || true
SCRIPT_DIR="$(dirname "$0")"
. "$SCRIPT_DIR/healthcheck_utils.sh"

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-5}

# Try health endpoint with API key if available
if [ -n "$DN_API_KEY" ]; then
  HEALTH_URL="http://localhost:5454/api/v1/health"
  
  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 --header="X-API-Key: $DN_API_KEY" "$HEALTH_URL" 2>/dev/null || echo "")
  END=$(date +%s)
  
  if [ -z "$RESPONSE" ]; then
    log_event "error" "Notifiarr API not responding"
    exit 1
  fi
  
  # Check for error in response
  if echo "$RESPONSE" | grep -qi "error\|fail"; then
    log_event "error" "Notifiarr health check failed: $RESPONSE"
    exit 1
  fi
  
  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    log_event "error" "Notifiarr API response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi
  
  log_event "healthy" "response_time=${RESPONSE_TIME}s (API check)"
else
  # Fallback to basic ping check
  PING_URL="http://localhost:5454/api/v1/ping"
  
  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 "$PING_URL" 2>/dev/null || echo "")
  END=$(date +%s)
  
  if [ -z "$RESPONSE" ]; then
    log_event "error" "Notifiarr not responding"
    exit 1
  fi
  
  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    log_event "error" "Notifiarr response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi
  
  log_event "healthy" "response_time=${RESPONSE_TIME}s (ping check)"
fi

exit 0
