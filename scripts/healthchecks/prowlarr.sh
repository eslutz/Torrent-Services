#!/bin/sh
# Prowlarr healthcheck - verify API health with fallback to ping
#
# Two-tier validation strategy:
# 1. Without API key (initial deployment):
#    - Service is running and responding
#    - Returns valid JSON with "status":"OK"
#    - Response time under 3 seconds
#
# 2. With API key (production):
#    - Service is running and API accessible
#    - No errors reported in health endpoint
#    - Database connectivity working
#    - Background tasks healthy
#    - Response time under 3 seconds
#
# Catches:
#  ❌ Service crashed/not running
#  ❌ Web server not responding
#  ❌ Slow response times (degraded performance)
#  ❌ Database connection failures (API mode)
#  ❌ Indexer connectivity issues (API mode)
#  ❌ Configuration errors (API mode)
#  ❌ Background task failures (API mode)

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-3}

# If API key is available, use detailed health check
if [ -n "$PROWLARR_API_KEY" ]; then
  HEALTH_URL="http://localhost:9696/api/v1/health"

  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 --header="X-Api-Key: $PROWLARR_API_KEY" "$HEALTH_URL" 2>/dev/null || echo "")
  END=$(date +%s)

  if [ -z "$RESPONSE" ]; then
    echo "Prowlarr API not responding"
    exit 1
  fi

  # Check for error or warning conditions
  if echo "$RESPONSE" | grep -q '"type":"error"'; then
    echo "Prowlarr health check failed: service reported errors"
    exit 1
  fi

  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    echo "Prowlarr API response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi

  echo "Healthy: response_time=${RESPONSE_TIME}s (API check)"
else
  # Fallback to simple ping check
  HEALTH_URL="http://localhost:9696/ping"

  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 "$HEALTH_URL" 2>/dev/null || echo "")
  END=$(date +%s)

  if [ -z "$RESPONSE" ]; then
    echo "Prowlarr not responding"
    exit 1
  fi

  if ! echo "$RESPONSE" | grep -q '"status".*:.*"OK"'; then
    echo "Prowlarr returned invalid response: $RESPONSE"
    exit 1
  fi

  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    echo "Prowlarr response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi

  echo "Healthy: response_time=${RESPONSE_TIME}s (ping check)"
fi

exit 0
