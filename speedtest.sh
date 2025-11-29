#!/bin/bash

# Internet Speed Test Script
# Tests download and upload speeds from the Transmission container

echo "=========================================="
echo "Internet Speed Test"
echo "=========================================="
echo ""

# Check current IP and location
echo "Connection Status:"
IP=$(docker exec transmission sh -c 'curl -s https://ipinfo.io/json | grep "\"ip\"" | cut -d"\"" -f4' 2>/dev/null)
CITY=$(docker exec transmission sh -c 'curl -s https://ipinfo.io/json | grep "\"city\"" | cut -d"\"" -f4' 2>/dev/null)
REGION=$(docker exec transmission sh -c 'curl -s https://ipinfo.io/json | grep "\"region\"" | cut -d"\"" -f4' 2>/dev/null)
COUNTRY=$(docker exec transmission sh -c 'curl -s https://ipinfo.io/json | grep "\"country\"" | cut -d"\"" -f4' 2>/dev/null)
ORG=$(docker exec transmission sh -c 'curl -s https://ipinfo.io/json | grep "\"org\"" | cut -d"\"" -f4' 2>/dev/null)

if [ -n "$IP" ]; then
    echo "IP: ${IP:-Unknown}"
    echo "Location: ${CITY:-Unknown}, ${REGION:-Unknown}, ${COUNTRY:-Unknown}"
    echo "ISP: ${ORG:-Unknown}"
else
    echo "⚠️  Connection check failed"
fi
echo ""

# Test download speed
echo "Testing download speed..."
DOWNLOAD_START=$(date +%s)

docker exec transmission sh -c "curl --progress-bar -o /tmp/speedtest.tmp http://speedtest.tele2.net/10MB.zip 2>&1"
DOWNLOAD_EXIT=$?
echo ""

# Calculate download speed from elapsed time (10MB file)
DOWNLOAD_END=$(date +%s)
DOWNLOAD_TIME=$((DOWNLOAD_END - DOWNLOAD_START))
if [ $DOWNLOAD_TIME -gt 0 ]; then
    # 10MB = 10485760 bytes
    SPEED_BPS=$((10485760 / DOWNLOAD_TIME))
    SPEED_KBPS=$((SPEED_BPS / 1024))
    SPEED_MBPS=$((SPEED_KBPS / 1024))
    
    if [ $SPEED_MBPS -gt 0 ]; then
        echo "✓ Download Speed: ${SPEED_MBPS} MB/s"
    else
        echo "✓ Download Speed: ${SPEED_KBPS} KB/s"
    fi
else
    echo "⚠️  Download speed measurement failed"
fi
echo ""

# Clean up
docker exec transmission rm -f /tmp/speedtest.tmp 2>/dev/null

# Test upload speed
echo "Testing upload speed..."
UPLOAD_START=$(date +%s)

docker exec transmission sh -c "dd if=/dev/zero of=/tmp/upload_test.tmp bs=1M count=10 2>/dev/null && curl --progress-bar -T /tmp/upload_test.tmp http://speedtest.tele2.net/upload.php -o /dev/null 2>&1 && rm -f /tmp/upload_test.tmp"
UPLOAD_EXIT=$?
echo ""
# Calculate upload speed from elapsed time (10MB file)
UPLOAD_END=$(date +%s)
UPLOAD_TIME=$((UPLOAD_END - UPLOAD_START))
if [ $UPLOAD_TIME -gt 0 ]; then
    # 10MB = 10485760 bytes
    SPEED_BPS=$((10485760 / UPLOAD_TIME))
    SPEED_KBPS=$((SPEED_BPS / 1024))
    SPEED_MBPS=$((SPEED_KBPS / 1024))
    
    if [ $SPEED_MBPS -gt 0 ]; then
        echo "✓ Upload Speed: ${SPEED_MBPS} MB/s"
    else
        echo "✓ Upload Speed: ${SPEED_KBPS} KB/s"
    fi
else
    echo "⚠️  Upload speed measurement failed"
fi
echo ""

# Clean up
docker exec transmission rm -f /tmp/upload_test.tmp 2>/dev/null

echo "=========================================="
echo "Note: Speed may be limited by:"
echo "  - ISP connection quality"
echo "  - Network congestion"
echo "  - Test server location/load"
echo "=========================================="
