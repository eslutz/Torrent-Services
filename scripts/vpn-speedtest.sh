#!/bin/bash

# Manual VPN sanity + throughput check from inside the qBittorrent container.
# What it does: compares host vs container public IP (to confirm VPN egress) and runs a quick
# download/upload test via curl against speedtest.tele2.net. Run ad-hoc; not wired into healthchecks.
# Tests download and upload speeds from the qBittorrent container
# Optimized for high-speed connections
CONTAINER_NAME="qbittorrent"
TEST_FILE_SIZE="50MB"
TEST_URL_DL="http://speedtest.tele2.net/${TEST_FILE_SIZE}.zip"
TEST_URL_UL="http://speedtest.tele2.net/upload.php"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Convert a size like 50MB or 1GB to bytes
bytes_from_size() {
    local size_str="$1"
    local number unit
    number=$(echo "$size_str" | sed 's/[^0-9.]//g')
    unit=$(echo "$size_str" | sed 's/[0-9.]//g' | tr '[:lower:]' '[:upper:]')

    case "$unit" in
        MB) awk -v n="$number" 'BEGIN {printf "%.0f", n * 1024 * 1024}' ;;
        GB) awk -v n="$number" 'BEGIN {printf "%.0f", n * 1024 * 1024 * 1024}' ;;
        KB) awk -v n="$number" 'BEGIN {printf "%.0f", n * 1024}' ;;
        B|"" ) awk -v n="$number" 'BEGIN {printf "%.0f", n}' ;;
        *) echo 0 ;;
    esac
}

# Simple spinner/progress with optional percent if a target size/path are provided
# Sets global SPINNER_ELAPSED_SECONDS with the total runtime in seconds
spinner() {
    local pid=$1
    local message=$2
    local total_bytes=${3:-0}
    local remote_path=$4
    local spin='|/-\\'
    local i=0
    local start=$(date +%s)
    SPINNER_ELAPSED_SECONDS=0

    tput civis 2>/dev/null
    while kill -0 "$pid" 2>/dev/null; do
        local now=$(date +%s)
        local elapsed=$((now - start))
        local percent=""

        if [ "$total_bytes" -gt 0 ] && [ -n "$remote_path" ]; then
            # Query size inside container; ignore errors
            local current_bytes
            current_bytes=$(docker exec $CONTAINER_NAME sh -c "stat -c%s $remote_path 2>/dev/null" 2>/dev/null || echo 0)
            if [ "$current_bytes" -gt 0 ]; then
                percent=$(awk -v c="$current_bytes" -v t="$total_bytes" 'BEGIN {printf " %5.1f%%", (c/t)*100}')
            fi
        fi

        printf "\r%b %s%s [%02dm:%02ds]" "$message" "${spin:i%${#spin}:1}" "$percent" $((elapsed / 60)) $((elapsed % 60))
        i=$(( (i + 1) % ${#spin} ))
        sleep 0.2
    done
    local end=$(date +%s)
    SPINNER_ELAPSED_SECONDS=$((end - start))
    printf "\r\033[K"
    tput cnorm 2>/dev/null
}

format_elapsed() {
    local seconds=${1:-0}
    printf "%02dm:%02ds" $((seconds / 60)) $((seconds % 60))
}

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

TEST_BYTES=$(bytes_from_size "$TEST_FILE_SIZE")

# Cleanup trap
cleanup() {
    docker exec $CONTAINER_NAME rm -f /tmp/speedtest.tmp /tmp/upload_test.tmp 2>/dev/null
}
trap cleanup EXIT

# Download Test with spinner
DL_TMP=$(mktemp)
docker exec $CONTAINER_NAME curl -L -s -w "%{speed_download}" -o /tmp/speedtest.tmp "$TEST_URL_DL" >"$DL_TMP" 2>/dev/null &
dl_pid=$!
spinner $dl_pid "${YELLOW}Testing Download...${NC}" "$TEST_BYTES" "/tmp/speedtest.tmp"
wait $dl_pid
DL_ELAPSED=$SPINNER_ELAPSED_SECONDS
DL_SPEED_BPS=$(cat "$DL_TMP")
rm -f "$DL_TMP"
printf "Testing Download... "

# Convert to Mbps (Bits per second / 1,000,000)
# curl gives bytes/sec. Multiply by 8 for bits, divide by 1,000,000 for Mbps.
# Using python for float math if available, or awk
if [ -n "$DL_SPEED_BPS" ]; then
    DL_MBPS=$(echo "$DL_SPEED_BPS" | awk '{printf "%.2f", $1 * 8 / 1000000}')
    echo -e "${GREEN}${DL_MBPS} Mbps${NC} [$(format_elapsed "$DL_ELAPSED")]"
else
    echo -e "${RED}Failed${NC} [$(format_elapsed "$DL_ELAPSED")]"
fi

# Upload Test with spinner
UL_TMP=$(mktemp)
# Create dummy file
docker exec $CONTAINER_NAME dd if=/dev/zero of=/tmp/upload_test.tmp bs=1M count=10 status=none
docker exec $CONTAINER_NAME curl -s -w "%{speed_upload}" -T /tmp/upload_test.tmp -o /dev/null "$TEST_URL_UL" >"$UL_TMP" 2>/dev/null &
ul_pid=$!
spinner $ul_pid "${YELLOW}Testing Upload...   ${NC}"
wait $ul_pid
UL_ELAPSED=$SPINNER_ELAPSED_SECONDS
UL_SPEED_BPS=$(cat "$UL_TMP")
rm -f "$UL_TMP"
printf "Testing Upload...   "

if [ -n "$UL_SPEED_BPS" ]; then
    UL_MBPS=$(echo "$UL_SPEED_BPS" | awk '{printf "%.2f", $1 * 8 / 1000000}')
    echo -e "${GREEN}${UL_MBPS} Mbps${NC} [$(format_elapsed "$UL_ELAPSED")]"
else
    echo -e "${RED}Failed${NC} [$(format_elapsed "$UL_ELAPSED")]"
fi

echo ""
echo "=========================================="
