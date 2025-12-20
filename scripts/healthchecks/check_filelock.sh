#!/bin/sh
# File lock healthcheck for any file (macOS compatible)
# Usage: SERVICE_NAME, FILE_PATH, LOG_PATH must be set
# Integrates with healthcheck_utils.sh for logging/email

SERVICE_NAME=${SERVICE_NAME}
FILE_PATH=${FILE_PATH}
LOG_PATH=${LOG_PATH}
LOCK_AGE_THRESHOLD=${LOCK_AGE_THRESHOLD}
EMAIL_TO=${EMAIL_TO}
SCRIPT_DIR="$(dirname "$0")"
. "$SCRIPT_DIR/healthcheck_utils.sh"

if [ -z "$FILE_PATH" ]; then
  log_event "error" "No FILE_PATH specified"
  exit 2
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
  log_event "healthy" "No lock file present: $FILE_PATH"
  exit 0
fi

# Get lock file age (seconds)
NOW=$(date +%s)

# Cross-platform stat command (Linux/GNU vs macOS/BSD)
if stat --version 2>/dev/null | grep -q "GNU"; then
    # Linux (Debian/Alpine)
    FILE_MTIME=$(stat -c %Y "$FILE_PATH")
else
    # macOS / BSD
    FILE_MTIME=$(stat -f %m "$FILE_PATH")
fi

AGE=$((NOW - FILE_MTIME))

if [ $AGE -ge $LOCK_AGE_THRESHOLD ]; then
  log_event "stale_lock" "Stale lock file detected ($FILE_PATH, age ${AGE}s), removing"
  rm -f "$FILE_PATH"
  log_event "remediation_requested" "{\"remediation_requested\": true, \"action\": \"remove_stale_lock\", \"file\": "$FILE_PATH"}"
  send_email "Stale lock removed" "Stale lock file $FILE_PATH removed for $SERVICE_NAME"
  exit 0
else
  log_event "lock_recent" "Lock file $FILE_PATH present but not stale (age ${AGE}s)"
  exit 1
fi
