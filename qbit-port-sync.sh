#!/bin/bash
# Automatically update qBittorrent listening port from Gluetun's forwarded port

# Attempt to install/update required packages
echo "Checking for package updates..."
if ! apk add --no-cache curl bash inotify-tools jq > /dev/null 2>&1; then
    if ! command -v curl &> /dev/null || ! command -v inotifywait &> /dev/null || ! command -v jq &> /dev/null; then
        echo "ERROR: Failed to install packages and tools are missing. Check internet connection."
        exit 1
    fi
    echo "Warning: Package update failed (likely offline), using existing tools."
fi

# Configuration
QBIT_CONNECTION_RETRIES=60
GLUETUN_CONNECTION_RETRIES=60
PORT_UPDATE_RETRIES=5
PORT_FILE="/tmp/gluetun/forwarded_port"
STATUS_FILE="/tmp/qbit-port-sync-status"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
}

error() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] ERROR: $1" >&2
}

validate_config() {
    # Ensure all required environment variables are set
    local missing=0
    if [ -z "$QBIT_HOST" ]; then error "QBIT_HOST is not set"; missing=1; fi
    if [ -z "$QBIT_USER" ]; then error "QBIT_USER is not set"; missing=1; fi
    if [ -z "$QBIT_PASS" ]; then error "QBIT_PASS is not set"; missing=1; fi

    if [ $missing -eq 1 ]; then
        exit 1
    fi
}

wait_for_gluetun() {
    # Poll for the existence of the port file from Gluetun
    log "Waiting for Gluetun port file..."
    local retries=0
    while [ ! -f "$PORT_FILE" ]; do
        sleep 5
        ((retries++))
        if [ $retries -gt $GLUETUN_CONNECTION_RETRIES ]; then
            error "Gluetun port file not found after $((GLUETUN_CONNECTION_RETRIES * 5)) seconds."
            return 1
        fi
    done
    log "Gluetun port file found."
    return 0
}

wait_for_qbittorrent() {
    # Poll qBittorrent API to ensure it's reachable
    log "Waiting for qBittorrent at $QBIT_HOST..."
    local retries=0
    while ! curl -s "http://${QBIT_HOST}/api/v2/app/version" > /dev/null; do
        sleep 5
        ((retries++))
        if [ $retries -gt $QBIT_CONNECTION_RETRIES ]; then
            error "qBittorrent is not reachable after $((QBIT_CONNECTION_RETRIES * 5)) seconds."
            return 1
        fi
    done
    log "qBittorrent is online."
    return 0
}

try_update_port() {
    # 1. Read and validate the forwarded port from file
    FORWARDED_PORT=$(cat "$PORT_FILE" 2>/dev/null | tr -d '\n\r')
    if [[ ! "$FORWARDED_PORT" =~ ^[0-9]+$ ]]; then
        error "Invalid port in file: '$FORWARDED_PORT'"
        return 1
    fi

    log "Gluetun forwarded port: $FORWARDED_PORT"

    # 2. Authenticate with qBittorrent and save cookie
    COOKIE_FILE=$(mktemp)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --cookie-jar "$COOKIE_FILE" \
        --header "Referer: http://${QBIT_HOST}" \
        --data "username=${QBIT_USER}&password=${QBIT_PASS}" \
        "http://${QBIT_HOST}/api/v2/auth/login")

    if [ "$HTTP_CODE" != "200" ]; then
        error "Authentication failed (HTTP $HTTP_CODE). Check credentials."
        rm -f "$COOKIE_FILE"
        return 1
    fi

    # 3. Get current listening port
    CURRENT_PREFS=$(curl -s --cookie "$COOKIE_FILE" "http://${QBIT_HOST}/api/v2/app/preferences")
    CURRENT_PORT=$(echo "$CURRENT_PREFS" | jq -r '.listen_port')

    if [ -z "$CURRENT_PORT" ] || [ "$CURRENT_PORT" = "null" ]; then
        error "Failed to retrieve current port configuration."
        rm -f "$COOKIE_FILE"
        return 1
    fi

    # 4. Compare and update if necessary
    if [ "$CURRENT_PORT" != "$FORWARDED_PORT" ]; then
        log "Port mismatch (Current: $CURRENT_PORT, New: $FORWARDED_PORT). Updating..."

        # Update port
        UPDATE_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://${QBIT_HOST}/api/v2/app/setPreferences" \
            --cookie "$COOKIE_FILE" \
            --data "json={\"listen_port\":${FORWARDED_PORT}}")

        if [ "$UPDATE_CODE" = "200" ]; then
            log "Successfully updated qBittorrent port to $FORWARDED_PORT"
        else
            error "Failed to update port (HTTP $UPDATE_CODE)."
            rm -f "$COOKIE_FILE"
            return 1
        fi
    else
        log "Port is already set to $FORWARDED_PORT. No action needed."
    fi

    rm -f "$COOKIE_FILE"
    return 0
}

update_port() {
    # Retry loop for port updates to handle transient failures
    for i in $(seq 1 $PORT_UPDATE_RETRIES); do
        if try_update_port; then
            echo "OK" > "$STATUS_FILE"
            return 0
        fi

        if [ "$i" -lt $PORT_UPDATE_RETRIES ]; then
            log "Update failed, retrying in 5 seconds ($i/$PORT_UPDATE_RETRIES)..."
            sleep 5
        else
            error "Update failed after $PORT_UPDATE_RETRIES attempts."
            echo "ERROR" > "$STATUS_FILE"
            return 1
        fi
    done
}

# Main execution
log "Starting qBittorrent port updater..."
echo "STARTING" > "$STATUS_FILE"

# 1. Validate configuration
log "Starting qBittorrent port updater..."
validate_config

# 2. Wait for Gluetun port file
if ! wait_for_gluetun; then
    exit 1
fi

# 3. Wait for qBittorrent to be online
if ! wait_for_qbittorrent; then
    exit 1
fi

# 4. Initial Update
update_port

# 5. Monitor for port change
log "Monitoring $PORT_FILE for changes..."
while true; do
    # Wait for file modification or creation
    inotifywait -q -e modify,create,moved_to "$PORT_FILE" 2>/dev/null

    # Debounce slightly
    sleep 2

    # Update with retries
    update_port
done
