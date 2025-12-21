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

# Lock age threshold (seconds) - only remediate if lock persists beyond this
LOCK_AGE_THRESHOLD=${LOCK_AGE_THRESHOLD:-300}

# State directory for tracking lock detection times
STATE_DIR="/tmp/sqlite_monitor_state"
mkdir -p "$STATE_DIR" 2>/dev/null || true
LOCK_STATE_FILE="$STATE_DIR/${SERVICE_NAME}_lock_detected_at"


check_sqlite_lock() {
    # Check for lock files or sqlite3 lock errors
    LOCK_DETECTED=0
    CURRENT_TIME=$(date +%s)
    
    # WAL/SHM files are NORMAL during database operations - don't panic
    if [ -f "$DB_PATH-wal" ] || [ -f "$DB_PATH-shm" ]; then
        LOCK_DETECTED=1
    fi
    
    # Try a simple query to check for actual lock errors
    if [ $LOCK_DETECTED -eq 0 ]; then
        sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | grep -q "database is locked"
        if [ $? -eq 0 ]; then
            LOCK_DETECTED=1
        fi
    fi
    
    # If lock detected, check duration
    if [ $LOCK_DETECTED -eq 1 ]; then
        if [ -f "$LOCK_STATE_FILE" ]; then
            LOCK_DETECTED_AT=$(cat "$LOCK_STATE_FILE")
            LOCK_AGE=$((CURRENT_TIME - LOCK_DETECTED_AT))
            
            if [ $LOCK_AGE -lt $LOCK_AGE_THRESHOLD ]; then
                log_event "lock_recent" "Lock detected but not stale (age ${LOCK_AGE}s < ${LOCK_AGE_THRESHOLD}s threshold)"
                return 0
            else
                log_event "lock_stale" "Lock persisted for ${LOCK_AGE}s (threshold: ${LOCK_AGE_THRESHOLD}s)"
                send_email "Stale lock detected" "Lock file present for $DB_PATH for ${LOCK_AGE}s"
                return 1
            fi
        else
            # First detection - record timestamp
            echo "$CURRENT_TIME" > "$LOCK_STATE_FILE"
            log_event "lock_detected" "Lock file present, starting timer"
            return 0
        fi
    else
        # No lock - clear state file if exists
        if [ -f "$LOCK_STATE_FILE" ]; then
            rm -f "$LOCK_STATE_FILE"
            log_event "lock_cleared" "Lock file cleared, resetting timer"
        fi
        return 0
    fi
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
    log_event "monitor_start" "Starting continuous monitor loop for $SERVICE_NAME (threshold: ${LOCK_AGE_THRESHOLD}s)"
    while true; do
        if check_sqlite_lock; then
            # Lock cleared or not stale - no action needed
            :
        else
            # Lock exceeded threshold - remediate
            log_event "monitor_issue" "Stale lock detected, attempting remediation"
            remediate
            # Clear state after remediation
            rm -f "$LOCK_STATE_FILE"
        fi
        sleep $MONITOR_INTERVAL
    done
fi

exit 0
