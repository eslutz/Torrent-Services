#!/bin/bash
# Automatically update qBittorrent listening port from Gluetun's forwarded port
# This script reads ProtonVPN's assigned port and configures qBittorrent automatically

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Get qBittorrent credentials from environment
QB_HOST="localhost:8080"
QB_USER="${QB_USER:-admin}"
QB_PASS="${QB_PASS}"

if [ -z "$QB_PASS" ]; then
    echo "❌ Error: QB_PASS not set in .env file"
    echo "   Add QB_PASS=your_qbittorrent_password to .env"
    exit 1
fi

# Get forwarded port from Gluetun
echo "Checking Gluetun for forwarded port..."
FORWARDED_PORT=$(docker exec gluetun cat /tmp/gluetun/forwarded_port 2>/dev/null)

if [ -z "$FORWARDED_PORT" ]; then
    echo "❌ Error: Could not get forwarded port from Gluetun"
    echo "   Make sure Gluetun is running and connected"
    exit 1
fi

echo "✓ Found forwarded port: $FORWARDED_PORT"

# Login to qBittorrent
COOKIE=$(curl -s -i --header "Referer: http://${QB_HOST}" \
    --data "username=${QB_USER}&password=${QB_PASS}" \
    "http://${QB_HOST}/api/v2/auth/login" | grep -i set-cookie | cut -d' ' -f2)

if [ -z "$COOKIE" ]; then
    echo "❌ Error: Failed to authenticate with qBittorrent"
    echo "   Check QB_USER and QB_PASS in .env file"
    exit 1
fi

# Get current port
CURRENT_PORT=$(curl -s --cookie "$COOKIE" \
    "http://${QB_HOST}/api/v2/app/preferences" | \
    grep -o '"listen_port":[0-9]*' | cut -d':' -f2)

echo "Current qBittorrent port: $CURRENT_PORT"

# Update if different
if [ "$CURRENT_PORT" != "$FORWARDED_PORT" ]; then
    echo "Updating qBittorrent listening port to: $FORWARDED_PORT"

    curl -s -X POST "http://${QB_HOST}/api/v2/app/setPreferences" \
        --cookie "$COOKIE" \
        --data "json={\"listen_port\":${FORWARDED_PORT}}"

    echo "✓ Successfully updated qBittorrent port to: $FORWARDED_PORT"
    echo "  Wait 1-2 minutes for connectivity check to complete"
else
    echo "✓ Port already correct: $FORWARDED_PORT"
fi
