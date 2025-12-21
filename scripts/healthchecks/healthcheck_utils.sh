#!/bin/sh
# Shared utilities for healthcheck scripts
# Provides: log_event(), send_email()

SCRIPT_DIR="$(dirname "$0")"

EMAIL_TO=${EMAIL_TO:-admin@example.com}

log_event() {
  EVENT="$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"$1\", \"details\": \"$2\"}"
  if [ -n "${LOG_PATH:-}" ]; then
    echo "$EVENT" >> "$LOG_PATH"
  fi
  echo "$EVENT"
  if [ "$1" = "error" ] || [ "$1" = "unhealthy" ]; then
    send_email "${SERVICE_NAME:-healthcheck} health: $1" "$2"
  fi
}

send_email() {
  SUBJECT="$1"
  BODY="$2"
  EMAIL_TO=${EMAIL_TO:-admin@example.com}
  MAX_EMAIL_RETRIES=3
  BACKOFF_BASE=2
  ATTEMPT=1
  while [ $ATTEMPT -le $MAX_EMAIL_RETRIES ]; do
    if command -v msmtp >/dev/null 2>&1; then
      printf "Subject: %s\nTo: %s\n\n%s\n" "$SUBJECT" "$EMAIL_TO" "$BODY" | msmtp -t "$EMAIL_TO" && return 0
    elif command -v mail >/dev/null 2>&1; then
      echo "$BODY" | mail -s "$SUBJECT" "$EMAIL_TO" && return 0
    elif command -v sendmail >/dev/null 2>&1; then
      printf "Subject: %s\n\n%s\n" "$SUBJECT" "$BODY" | sendmail -t "$EMAIL_TO" && return 0
    else
      echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"email_failed\", \"details\": \"No mail/sendmail available to send: $SUBJECT\"}"
      return 1
    fi
    # If failed, log and backoff
    echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"email_retry_failed\", \"details\": \"Attempt $ATTEMPT failed for: $SUBJECT\"}"
    # POSIX sh compatible: 2^ATTEMPT via loop
    SLEEP_TIME=1
    i=0
    while [ $i -lt $ATTEMPT ]; do
      SLEEP_TIME=$((SLEEP_TIME * BACKOFF_BASE))
      i=$((i + 1))
    done
    sleep $SLEEP_TIME
    ATTEMPT=$((ATTEMPT+1))
  done
  echo "$(date -Iseconds) {\"service\": \"${SERVICE_NAME:-unknown}\", \"event\": \"email_failed\", \"details\": \"All retries failed for: $SUBJECT\"}"
  return 1
}

return 0
