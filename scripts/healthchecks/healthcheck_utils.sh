#!/bin/sh
# Shared utilities for healthcheck scripts
# Provides: log_event(), send_notification()

# Apprise configuration
APPRISE_URL=${APPRISE_URL:-http://apprise:8000}
APPRISE_HEALTHCHECK_TAG=${APPRISE_HEALTHCHECK_TAG:-health-alerts}
APPRISE_CONFIG_MODE=${APPRISE_CONFIG_MODE:-persistent}
APPRISE_STATELESS_URLS=${APPRISE_STATELESS_URLS:-}

log_event() {
  EVENT="$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"$1\", \"details\": \"$2\"}"
  if [ -n "${LOG_PATH:-}" ]; then
    echo "$EVENT" >> "$LOG_PATH"
  fi
  echo "$EVENT"
  if [ "$1" = "error" ] || [ "$1" = "unhealthy" ]; then
    send_notification "${SERVICE_NAME:-healthcheck} health: $1" "$2"
  fi
}

send_notification() {
  TITLE="$1"
  BODY="$2"
  MAX_RETRIES=3
  BACKOFF_BASE=2
  ATTEMPT=1

  # Determine Apprise endpoint based on configuration mode
  if [ "$APPRISE_CONFIG_MODE" = "stateless" ] && [ -n "$APPRISE_STATELESS_URLS" ]; then
    # Stateless mode: send directly with URLs in query param
    ENDPOINT="${APPRISE_URL}/notify"
    NOTIFY_PAYLOAD="{\"urls\":\"${APPRISE_STATELESS_URLS}\",\"title\":\"${TITLE}\",\"body\":\"${BODY}\",\"type\":\"warning\"}"
  else
    # Persistent mode: use named config tag
    ENDPOINT="${APPRISE_URL}/notify/${APPRISE_HEALTHCHECK_TAG}"
    NOTIFY_PAYLOAD="{\"title\":\"${TITLE}\",\"body\":\"${BODY}\",\"type\":\"warning\"}"
  fi

  while [ "$ATTEMPT" -le "$MAX_RETRIES" ]; do
    if command -v curl >/dev/null 2>&1; then
      RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "$NOTIFY_PAYLOAD" 2>&1)
      HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
      
      if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
        echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_sent\", \"details\": \"Sent via Apprise: $TITLE\"}"
        return 0
      fi
      
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_retry_failed\", \"details\": \"Attempt $ATTEMPT failed with HTTP $HTTP_CODE: $TITLE\"}"
    elif command -v wget >/dev/null 2>&1; then
      if wget --post-data="$NOTIFY_PAYLOAD" \
             --header="Content-Type: application/json" \
             -O- "$ENDPOINT" >/dev/null 2>&1; then
        echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_sent\", \"details\": \"Sent via Apprise: $TITLE\"}"
        return 0
      fi
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_retry_failed\", \"details\": \"Attempt $ATTEMPT failed: $TITLE\"}"
    else
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_failed\", \"details\": \"No curl/wget available to send: $TITLE\"}"
      return 1
    fi
    
    # Exponential backoff
    SLEEP_TIME=1
    i=0
    while [ "$i" -lt "$ATTEMPT" ]; do
      SLEEP_TIME=$((SLEEP_TIME * BACKOFF_BASE))
      i=$((i + 1))
    done
    sleep "$SLEEP_TIME"
    ATTEMPT=$((ATTEMPT+1))
  done
  
  echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_failed\", \"details\": \"All retries failed for: $TITLE\"}"
  return 1
}

# Legacy alias for backward compatibility
send_email() {
  send_notification "$@"
}

return 0
