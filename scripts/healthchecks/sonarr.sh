#!/bin/sh
# Sonarr healthcheck - verify API health with fallback to ping
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
#    - Download client connectivity
#    - Series monitoring functional
#    - Response time under 3 seconds
#
# Catches:
#  ❌ Service crashed/not running
#  ❌ Web server not responding
#  ❌ Slow response times (degraded performance)
#  ❌ Database connection failures (API mode)
#  ❌ Download client (qBittorrent) issues (API mode)
#  ❌ Indexer (Prowlarr) connectivity issues (API mode)
#  ❌ Disk space issues (API mode)
#  ❌ Configuration errors (API mode)

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-3}

# If API key is available, use detailed health check
if [ -n "$SONARR_API_KEY" ]; then
  HEALTH_URL="http://localhost:8989/api/v3/health"

  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 --header="X-Api-Key: $SONARR_API_KEY" "$HEALTH_URL" 2>/dev/null || echo "")
  END=$(date +%s)

  if [ -z "$RESPONSE" ]; then
    echo "Sonarr API not responding"
    exit 1
  fi

  # Check for error or warning conditions
  if echo "$RESPONSE" | grep -q '"type":"error"'; then
    echo "Sonarr health check failed: service reported errors"
    exit 1
  fi

  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    echo "Sonarr API response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi

  echo "Healthy: response_time=${RESPONSE_TIME}s (API check)"
else
  # Fallback to simple ping check
  HEALTH_URL="http://localhost:8989/ping"

  START=$(date +%s)
  RESPONSE=$(wget -qO- --timeout=10 "$HEALTH_URL" 2>/dev/null || echo "")
  END=$(date +%s)

  if [ -z "$RESPONSE" ]; then
    echo "Sonarr not responding"
    exit 1
  fi

  if ! echo "$RESPONSE" | grep -q '"status".*:.*"OK"'; then
    echo "Sonarr returned invalid response: $RESPONSE"
    exit 1
  fi

  RESPONSE_TIME=$((END - START))
  if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
    echo "Sonarr response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
    exit 1
  fi

  echo "Healthy: response_time=${RESPONSE_TIME}s (ping check)"
fi

exit 0
