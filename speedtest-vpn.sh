#!/bin/bash

# VPN Speed Test Script
# Tests download and upload speeds through the VPN connection used by qBittorrent

echo "=========================================="
echo "VPN Speed Test (via Gluetun container)"
echo "=========================================="
echo ""

# Check VPN IP and location
echo "VPN Status:"
VPN_INFO=$(docker exec gluetun wget -qO- https://am.i.mullvad.net/json 2>/dev/null)
if [ $? -eq 0 ]; then
    # Parse JSON using sed (works on macOS and Linux)
    VPN_IP=$(echo "$VPN_INFO" | sed -n 's/.*"ip":"\([^"]*\)".*/\1/p')
    VPN_CITY=$(echo "$VPN_INFO" | sed -n 's/.*"city":"\([^"]*\)".*/\1/p')
    VPN_COUNTRY=$(echo "$VPN_INFO" | sed -n 's/.*"country":"\([^"]*\)".*/\1/p')
    VPN_ORG=$(echo "$VPN_INFO" | sed -n 's/.*"organization":"\([^"]*\)".*/\1/p')
    
    echo "IP: ${VPN_IP:-Unknown}"
    echo "Location: ${VPN_CITY:-Unknown}, ${VPN_COUNTRY:-Unknown}"
    echo "Organization: ${VPN_ORG:-Unknown}"
else
    echo "⚠️  VPN connection check failed"
fi
echo ""

# Test download speed
echo "Testing download speed..."
echo "Downloading 10MB test file..."
DOWNLOAD_START_EPOCH=$(date +%s)

# Run download in background and show progress
(docker exec gluetun sh -c "
    wget --output-document=/tmp/speedtest.tmp http://speedtest.tele2.net/10MB.zip 2>&1
    rm -f /tmp/speedtest.tmp
" > /tmp/download_output.txt 2>&1) &
DOWNLOAD_PID=$!

# Show elapsed time while download is running
while kill -0 $DOWNLOAD_PID 2>/dev/null; do
    ELAPSED=$(($(date +%s) - DOWNLOAD_START_EPOCH))
    printf "\rElapsed time: %02dm:%02ds" $((ELAPSED/60)) $((ELAPSED%60))
    sleep 1
done
wait $DOWNLOAD_PID  # Ensure process fully completes
echo ""

DOWNLOAD_OUTPUT=$(cat /tmp/download_output.txt)
rm -f /tmp/download_output.txt

# Extract download speed from wget output
DOWNLOAD_SPEED=$(echo "$DOWNLOAD_OUTPUT" | grep -o '([0-9.]*[[:space:]]*[KMG]B/s)' | tail -1 | tr -d '()')
if [ -n "$DOWNLOAD_SPEED" ]; then
    echo "✓ Download Speed: $DOWNLOAD_SPEED"
else
    echo "⚠️  Download speed measurement failed"
fi
echo ""

# Test upload speed
echo "Testing upload speed..."
echo "Uploading 10MB test file..."
UPLOAD_START_EPOCH=$(date +%s)

# Run upload in background and show progress
(docker exec gluetun sh -c "
    dd if=/dev/zero of=/tmp/upload_test.tmp bs=1M count=10 2>/dev/null
    wget --post-file=/tmp/upload_test.tmp --output-document=/dev/null http://speedtest.tele2.net/upload.php 2>&1
    rm -f /tmp/upload_test.tmp
" > /tmp/upload_output.txt 2>&1) &
UPLOAD_PID=$!

# Show elapsed time while upload is running
while kill -0 $UPLOAD_PID 2>/dev/null; do
    ELAPSED=$(($(date +%s) - UPLOAD_START_EPOCH))
    printf "\rElapsed time: %02dm:%02ds" $((ELAPSED/60)) $((ELAPSED%60))
    sleep 1
done
wait $UPLOAD_PID  # Ensure process fully completes
echo ""

UPLOAD_OUTPUT=$(cat /tmp/upload_output.txt)
rm -f /tmp/upload_output.txt

# Extract upload speed from wget output
UPLOAD_SPEED=$(echo "$UPLOAD_OUTPUT" | grep -o '([0-9.]*[[:space:]]*[KMG]B/s)' | tail -1 | tr -d '()')
if [ -n "$UPLOAD_SPEED" ]; then
    echo "✓ Upload Speed: $UPLOAD_SPEED"
else
    echo "⚠️  Upload speed measurement failed"
fi
echo ""

echo "=========================================="
echo "Note: Speed may be limited by:"
echo "  - VPN server location/load"
echo "  - Your ISP connection"
echo "  - Time of day / network congestion"
echo "  - Mullvad has no port forwarding (affects P2P)"
echo "=========================================="
