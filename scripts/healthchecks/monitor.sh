#!/bin/sh
# Multi-service DB/file lock monitor runner
# Reads monitors.json and launches a monitor loop for each job
# Usage: sh /scripts/monitor.sh

CONFIG_PATH="/scripts/monitors.json"
SCRIPT_DIR="$(dirname "$0")"

if ! [ -f "$CONFIG_PATH" ]; then
  echo "Config file $CONFIG_PATH not found" >&2
  exit 1
fi

# Requires jq for JSON parsing
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found; install jq in monitor container" >&2
  exit 1
fi

# Read jobs from config
JOBS=$(jq -c '.[]' "$CONFIG_PATH")

run_sqlite_monitor() {
  SERVICE_NAME="$1"
  DB_PATH="$2"
  INTERVAL="$3"
  LOCK_AGE_THRESHOLD="$4"
  LOG_DIR="/logs/${SERVICE_NAME}"
  mkdir -p "$LOG_DIR" 2>/dev/null || true
  LOG_PATH="${LOG_DIR}/healthcheck.log"
  while true; do
    SERVICE_NAME="$SERVICE_NAME" DB_PATH="$DB_PATH" LOG_PATH="$LOG_PATH" MONITOR_INTERVAL="$INTERVAL" LOCK_AGE_THRESHOLD="$LOCK_AGE_THRESHOLD" sh "$SCRIPT_DIR/check_sqlite.sh" monitor
    sleep "$INTERVAL"
  done
}

run_filelock_monitor() {
  SERVICE_NAME="$1"
  FILE_PATH="$2"
  INTERVAL="$3"
  LOG_DIR="/logs/${SERVICE_NAME}"
  mkdir -p "$LOG_DIR" 2>/dev/null || true
  LOG_PATH="${LOG_DIR}/healthcheck.log"
  LOCK_AGE_THRESHOLD="$4"
  while true; do
    SERVICE_NAME="$SERVICE_NAME" FILE_PATH="$FILE_PATH" LOG_PATH="$LOG_PATH" LOCK_AGE_THRESHOLD="$LOCK_AGE_THRESHOLD" sh "$SCRIPT_DIR/check_filelock.sh"
    sleep "$INTERVAL"
  done
}

for JOB in $JOBS; do
  TYPE=$(echo "$JOB" | jq -r '.type')
  SERVICE=$(echo "$JOB" | jq -r '.service')
  INTERVAL=$(echo "$JOB" | jq -r '.check_interval')
  if [ "$TYPE" = "sqlite" ]; then
    DB=$(echo "$JOB" | jq -r '.db')
    LOCK_AGE_THRESHOLD=$(echo "$JOB" | jq -r '.lock_age_threshold // 300')
    echo "Starting sqlite monitor for $SERVICE ($DB) every $INTERVAL sec, lock_age_threshold=$LOCK_AGE_THRESHOLD" >&2
    run_sqlite_monitor "$SERVICE" "$DB" "$INTERVAL" "$LOCK_AGE_THRESHOLD" &
  elif [ "$TYPE" = "filelock" ]; then
    FILE=$(echo "$JOB" | jq -r '.file')
    LOCK_AGE_THRESHOLD=$(echo "$JOB" | jq -r '.lock_age_threshold // 300')
    echo "Starting filelock monitor for $SERVICE ($FILE) every $INTERVAL sec, lock_age_threshold=$LOCK_AGE_THRESHOLD" >&2
    run_filelock_monitor "$SERVICE" "$FILE" "$INTERVAL" "$LOCK_AGE_THRESHOLD" &
  fi
  # Future: add other types (file lock, etc)
done

wait
