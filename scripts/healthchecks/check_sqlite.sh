#!/bin/sh
# Healthcheck for SQLite file locks and errors with auto-remediation, logging, and email notification
# Service-specific paths should be set via env vars or script args

SERVICE_NAME=${SERVICE_NAME}
DB_PATH=${DB_PATH}
LOG_PATH=${LOG_PATH}
MAX_RETRIES=${MAX_RETRIES}
BACKOFF_BASE=${BACKOFF_BASE}
EMAIL_TO=${EMAIL_TO}
RETRY_COUNT=0
SCRIPT_DIR="$(dirname "$0")"
. "$SCRIPT_DIR/healthcheck_utils.sh"

# Monitor mode: long-running loop to actively watch DB and remediate
MONITOR_INTERVAL=${MONITOR_INTERVAL}


check_sqlite_lock() {
    # Check for lock files or sqlite3 lock errors
    if [ -f "$DB_PATH-wal" ] || [ -f "$DB_PATH-shm" ]; then
        log_event "lock_detected" "Lock file present"
        send_email "Lock detected" "Lock file present for $DB_PATH"
        return 1
    fi
    # Try a simple query
    sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | grep -q "database is locked"
    if [ $? -eq 0 ]; then
        log_event "sqlite_locked" "Database is locked error"
        send_email "SQLite locked" "Database is locked for $DB_PATH"
        return 1
    fi
    return 0
}

remediate() {
    log_event "remediation_attempt" "Attempting remediation"
    # Emit remediation request to trigger external restart (e.g. autoheal)
    # We do NOT delete WAL/SHM files here to avoid corruption. 
    # The service restart should handle cleanup.
    log_event "remediation_requested" "{\"remediation_requested\": true, \"action\": \"restart_service\"}"
    
    if command -v docker >/dev/null 2>&1; then
        log_event "remediation_action" "Restarting container $SERVICE_NAME"
        docker restart "$SERVICE_NAME"
    else
        log_event "remediation_error" "Docker command not found, cannot restart service"
    fi
    
    send_email "Remediation requested" "SQLite lock detected for $DB_PATH; requesting service restart for $SERVICE_NAME"
}


# Single probe/remediation attempt (wrapper handles retries)
# Only run this if NOT in monitor mode
if [ "${1:-}" != "monitor" ]; then
    check_sqlite_lock
    if [ $? -eq 0 ]; then
        log_event "healthy" "No lock detected"
        exit 0
    fi
    remediate
    log_event "unhealthy" "Unhealthy after single remediation attempt"
    send_email "Unhealthy" "Unhealthy after single remediation attempt for $SERVICE_NAME, manual intervention required."
    exit 1
fi

## If called in monitor mode (long-running), run continuous checks
if [ "${1:-}" = "monitor" ]; then
    log_event "monitor_start" "Starting continuous monitor loop for $SERVICE_NAME"
    while true; do
        if check_sqlite_lock; then
            # Optional: Don't log every success to avoid spamming logs, or log periodically
            :
        else
            log_event "monitor_issue" "Issue detected, attempting remediation"
            remediate
        fi
        sleep $MONITOR_INTERVAL
    done
fi

exit 0
