#!/bin/bash
# Automatically update Transmission listening port from Gluetun's forwarded port
# This script reads ProtonVPN's assigned port and configures Transmission automatically

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Get Transmission credentials from environment
TRANSMISSION_HOST="localhost:9091"
TRANSMISSION_USER="${TRANSMISSION_USER:-admin}"
TRANSMISSION_PASS="${TRANSMISSION_PASS}"

if [ -z "$TRANSMISSION_PASS" ]; then
    echo "❌ Error: TRANSMISSION_PASS not set in .env file"
    echo "   Add TRANSMISSION_PASS=your_transmission_password to .env"
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

# Get session ID for Transmission RPC
SESSION_ID=$(curl -s -u "${TRANSMISSION_USER}:${TRANSMISSION_PASS}" \
    "http://${TRANSMISSION_HOST}/transmission/rpc" 2>/dev/null | \
    grep -oP "X-Transmission-Session-Id: \K[^<]+")

if [ -z "$SESSION_ID" ]; then
    echo "❌ Error: Failed to get Transmission session ID"
    echo "   Check TRANSMISSION_USER and TRANSMISSION_PASS in .env file"
    exit 1
fi

# Get current port from Transmission
CURRENT_PORT=$(curl -s -u "${TRANSMISSION_USER}:${TRANSMISSION_PASS}" \
    -H "X-Transmission-Session-Id: ${SESSION_ID}" \
    -d '{"method":"session-get","arguments":{"fields":["peer-port"]}}' \
    "http://${TRANSMISSION_HOST}/transmission/rpc" 2>/dev/null | \
    grep -oP '"peer-port":\K[0-9]+')

echo "Current Transmission port: $CURRENT_PORT"

# Update if different
if [ "$CURRENT_PORT" != "$FORWARDED_PORT" ]; then
    echo "Updating Transmission listening port to: $FORWARDED_PORT"

    curl -s -u "${TRANSMISSION_USER}:${TRANSMISSION_PASS}" \
        -H "X-Transmission-Session-Id: ${SESSION_ID}" \
        -d "{\"method\":\"session-set\",\"arguments\":{\"peer-port\":${FORWARDED_PORT}}}" \
        "http://${TRANSMISSION_HOST}/transmission/rpc"

    echo "✓ Successfully updated Transmission port to: $FORWARDED_PORT"
    echo "  Wait 1-2 minutes for connectivity check to complete"
else
    echo "✓ Port already correct: $FORWARDED_PORT"
fi
