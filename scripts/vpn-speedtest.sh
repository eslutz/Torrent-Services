#!/bin/bash

# Manual VPN sanity + throughput check from inside the qBittorrent container.
# What it does: compares host vs container public IP (to confirm VPN egress) and runs a quick
# download/upload test via curl against speedtest.tele2.net. Run ad-hoc; not wired into healthchecks.
# Tests download and upload speeds from the qBittorrent container
# Optimized for high-speed connections
CONTAINER_NAME="qbittorrent"
TEST_FILE_SIZE="100MB"
TEST_URL_DL="http://speedtest.tele2.net/${TEST_FILE_SIZE}.zip"
TEST_URL_UL="http://speedtest.tele2.net/upload.php"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "VPN & Speed Test Diagnostic"
echo "=========================================="

# 1. Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Error: Container '${CONTAINER_NAME}' is not running.${NC}"
    exit 1
fi

# 2. VPN Status Check (Compare Host vs Container)
echo -e "\n--- 🔒 VPN Status ---"

# Get Host IP (ISP)
HOST_IP=$(curl -s https://ipinfo.io/json | grep '"ip"' | cut -d'"' -f4)
# Get Container IP (VPN)
CONTAINER_JSON=$(docker exec $CONTAINER_NAME curl -s https://ipinfo.io/json)
CONTAINER_IP=$(echo "$CONTAINER_JSON" | grep '"ip"' | cut -d'"' -f4)
CITY=$(echo "$CONTAINER_JSON" | grep '"city"' | cut -d'"' -f4)
COUNTRY=$(echo "$CONTAINER_JSON" | grep '"country"' | cut -d'"' -f4)
ORG=$(echo "$CONTAINER_JSON" | grep '"org"' | cut -d'"' -f4)

echo "Host IP (ISP):      $HOST_IP"
echo "Container IP (VPN): $CONTAINER_IP"

if [ "$HOST_IP" != "$CONTAINER_IP" ] && [ -n "$CONTAINER_IP" ]; then
    echo -e "Status:             ${GREEN}SECURE (IPs are different)${NC}"
    echo "Location:           $CITY, $COUNTRY"
    echo "Provider:           $ORG"
else
    echo -e "Status:             ${RED}WARNING: IPs match or lookup failed! VPN might be down.${NC}"
fi

# 3. Speed Test
echo -e "\n--- 🚀 Speed Test (${TEST_FILE_SIZE}) ---"

# Cleanup trap
cleanup() {
    docker exec $CONTAINER_NAME rm -f /tmp/speedtest.tmp /tmp/upload_test.tmp 2>/dev/null
}
trap cleanup EXIT

# Download Test
echo -ne "${YELLOW}Testing Download... ${NC}"
# Use curl write-out for exact speed calculation
DL_SPEED_BPS=$(docker exec $CONTAINER_NAME curl -L -s -w "%{speed_download}" -o /tmp/speedtest.tmp "$TEST_URL_DL")

# Convert to Mbps (Bits per second / 1,000,000)
# curl gives bytes/sec. Multiply by 8 for bits, divide by 1,000,000 for Mbps.
# Using python for float math if available, or awk
if [ -n "$DL_SPEED_BPS" ]; then
    DL_MBPS=$(echo "$DL_SPEED_BPS" | awk '{printf "%.2f", $1 * 8 / 1000000}')
    echo -e "${GREEN}${DL_MBPS} Mbps${NC}"
else
    echo -e "${RED}Failed${NC}"
fi

# Upload Test
echo -ne "${YELLOW}Testing Upload...   ${NC}"
# Create dummy file
docker exec $CONTAINER_NAME dd if=/dev/zero of=/tmp/upload_test.tmp bs=1M count=10 status=none
UL_SPEED_BPS=$(docker exec $CONTAINER_NAME curl -s -w "%{speed_upload}" -T /tmp/upload_test.tmp -o /dev/null "$TEST_URL_UL")

if [ -n "$UL_SPEED_BPS" ]; then
    UL_MBPS=$(echo "$UL_SPEED_BPS" | awk '{printf "%.2f", $1 * 8 / 1000000}')
    echo -e "${GREEN}${UL_MBPS} Mbps${NC}"
else
    echo -e "${RED}Failed${NC}"
fi

echo ""
echo "=========================================="
