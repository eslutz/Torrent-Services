#!/bin/sh
# Shared utilities for healthcheck scripts
# Provides: log_event(), send_notification()

# Email configuration (SMTP via msmtp)
EMAIL_TO=${EMAIL_TO:-}
SMTP_HOST=${SMTP_HOST:-smtp.mail.me.com}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USER=${SMTP_USER:-}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
SMTP_FROM=${SMTP_FROM:-}

# Rate limiting configuration
NOTIFICATION_COOLDOWN=${NOTIFICATION_COOLDOWN:-300}  # 5 minutes default
NOTIFICATION_STATE_DIR=${NOTIFICATION_STATE_DIR:-/tmp/notification_state}
mkdir -p "$NOTIFICATION_STATE_DIR" 2>/dev/null || true

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

should_send_notification() {
  NOTIFICATION_KEY="$1"
  STATE_FILE="${NOTIFICATION_STATE_DIR}/${NOTIFICATION_KEY}"
  CURRENT_TIME=$(date +%s)

  # Check if notification was recently sent
  if [ -f "$STATE_FILE" ]; then
    LAST_SENT=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
    TIME_DIFF=$((CURRENT_TIME - LAST_SENT))

    if [ "$TIME_DIFF" -lt "$NOTIFICATION_COOLDOWN" ]; then
      REMAINING=$((NOTIFICATION_COOLDOWN - TIME_DIFF))
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_throttled\", \"details\": \"Throttled: $NOTIFICATION_KEY (${REMAINING}s remaining)\"}"
      return 1
    fi
  fi

  # Update state file with current timestamp
  echo "$CURRENT_TIME" > "$STATE_FILE"
  return 0
}

send_notification() {
  TITLE="$1"
  BODY="$2"

  # Skip if email not configured
  if [ -z "$EMAIL_TO" ] || [ -z "$SMTP_USER" ] || [ -z "$SMTP_PASSWORD" ]; then
    echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_skipped\", \"details\": \"Email not configured (missing EMAIL_TO, SMTP_USER, or SMTP_PASSWORD)\"}"
    return 0
  fi

  # Generate notification key for deduplication (sanitize title)
  NOTIFICATION_KEY=$(echo "${TITLE}" | tr -cs '[:alnum:]' '_' | tr '[:upper:]' '[:lower:]')

  # Check rate limit
  if ! should_send_notification "$NOTIFICATION_KEY"; then
    return 0
  fi

  MAX_RETRIES=3
  BACKOFF_BASE=2
  ATTEMPT=1

  while [ "$ATTEMPT" -le "$MAX_RETRIES" ]; do
    # Create msmtp config in temp file
    MSMTP_CONFIG=$(mktemp)
    cat > "$MSMTP_CONFIG" << EOF
defaults
auth on
tls on
tls_starttls on
tls_certcheck on
logfile /dev/null
timeout 15

account default
host $SMTP_HOST
port $SMTP_PORT
from $SMTP_FROM
user $SMTP_USER
password $SMTP_PASSWORD
EOF
    chmod 600 "$MSMTP_CONFIG"

    # Send email using msmtp
    if command -v msmtp >/dev/null 2>&1; then
      EMAIL_RESULT=$(printf "To: %s\nFrom: %s\nSubject: [Torrent Services] %s\nContent-Type: text/plain; charset=utf-8\n\n%s\n\n--\nSent from: %s\nTimestamp: %s" \
        "$EMAIL_TO" "$SMTP_FROM" "$TITLE" "$BODY" "${SERVICE_NAME:-healthcheck}" "$(date -Iseconds)" | \
        msmtp -C "$MSMTP_CONFIG" "$EMAIL_TO" 2>&1)
      EXIT_CODE=$?
      rm -f "$MSMTP_CONFIG"

      if [ $EXIT_CODE -eq 0 ]; then
        echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_sent\", \"details\": \"Email sent: $TITLE\"}"
        return 0
      fi

      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_retry_failed\", \"details\": \"Attempt $ATTEMPT failed: $EMAIL_RESULT\"}"
    else
      rm -f "$MSMTP_CONFIG"
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"notification_failed\", \"details\": \"msmtp not available to send: $TITLE\"}"
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
