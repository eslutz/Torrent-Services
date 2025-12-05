#!/bin/sh
# qBittorrent healthcheck - verify web UI is responding
#
# Validates:
#  - Service is running and responding
#  - Web UI accessible (returns HTTP 200 or 403)
#  - Response time under 3 seconds
#
# Note: 403 (Forbidden) is considered healthy because it means
# the service is running but requires authentication
#
# Catches:
#  ❌ Service crashed/not running
#  ❌ Web UI not responding
#  ❌ Slow response times (degraded performance)
#  ❌ Complete service failure (no HTTP response)

set -e

MAX_RESPONSE_TIME=${MAX_RESPONSE_TIME:-3}

# qBittorrent requires auth but we check if port is listening and responsive
# A 403 response means service is running (just requires auth)
START=$(date +%s)
HTTP_CODE=$(wget --spider --server-response http://localhost:8080/api/v2/app/version 2>&1 | grep "^  HTTP/" | tail -1 | awk '{print $2}' || echo "000")
END=$(date +%s)

# Accept 200 (success) or 403 (requires auth but service is running)
if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "403" ]; then
  echo "qBittorrent not responding or returning error: HTTP $HTTP_CODE"
  exit 1
fi

# Check response time
RESPONSE_TIME=$((END - START))
if [ "$RESPONSE_TIME" -gt "$MAX_RESPONSE_TIME" ]; then
  echo "qBittorrent response too slow: ${RESPONSE_TIME}s (max ${MAX_RESPONSE_TIME}s)"
  exit 1
fi

echo "Healthy: response_time=${RESPONSE_TIME}s, http_code=$HTTP_CODE"
exit 0
