#!/bin/bash

# VPN Speed Test Script
# Tests download speed through the VPN connection used by qBittorrent

echo "=========================================="
echo "VPN Speed Test (via qBittorrent container)"
echo "=========================================="
echo ""

# Check VPN IP and location
echo "VPN Status:"
docker exec gluetun wget -qO- http://localhost:8000/v1/publicip/ip 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "VPN info unavailable"
echo ""

# Run speed test
echo "Running speed test (this may take 30-60 seconds)..."
echo ""

# Test download speed using a 100MB file
docker exec qbittorrent sh -c "
    echo 'Testing download speed...'
    START=\$(date +%s)
    wget -O /dev/null http://speedtest.tele2.net/100MB.zip 2>&1 | tail -2
    END=\$(date +%s)
    echo \"Test completed in \$((END-START)) seconds\"
" 2>/dev/null

echo ""
echo "=========================================="
echo "Note: Speed may be limited by:"
echo "  - VPN server location/load"
echo "  - Your ISP connection"
echo "  - Lack of port forwarding (affects torrents)"
echo "=========================================="
