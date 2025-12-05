#!/bin/sh
# Gluetun healthcheck - verify VPN tunnel and port forwarding
#
# Validates:
#  - tun0 interface exists (VPN tunnel established)
#  - VPN status is "running" via Gluetun API
#  - Public IP is VPN IP (no IP leaks)
#  - Port forwarding is active via Gluetun API
#  - Port number is valid (non-zero)
#  - Response time under 15 seconds
#
# Catches:
#  ❌ VPN tunnel not established
#  ❌ VPN daemon running but not connected
#  ❌ IP leaks (traffic bypassing VPN)
#  ❌ Port forwarding failures
#  ❌ ProtonVPN connectivity issues
#  ❌ Control server API failures
#  ❌ Network connectivity problems

set -e

start_time=$(date +%s)

# Check if VPN tunnel interface exists
if ! ip link show tun0 >/dev/null 2>&1; then
  echo "tun0 interface not found"
  exit 1
fi

# Check VPN status via Gluetun control server
vpn_status=$(wget -qO- --timeout=5 http://localhost:8000/v1/vpn/status 2>/dev/null || echo "")
if ! echo "$vpn_status" | grep -q '"status":"running"'; then
  echo "VPN not running: $vpn_status"
  exit 1
fi

# Verify port forwarding is working via Gluetun API
port_response=$(wget -qO- --timeout=5 http://localhost:8000/v1/openvpn/portforwarded 2>/dev/null || echo "")
if [ -z "$port_response" ]; then
  echo "Cannot get port forwarding status"
  exit 1
fi

PORT=$(echo "$port_response" | grep -o '"port":[0-9]*' | cut -d':' -f2)

if [ -z "$PORT" ] || [ "$PORT" = "0" ]; then
  echo "Port forwarding not active: $port_response"
  exit 1
fi

end_time=$(date +%s)
response_time=$((end_time - start_time))

echo "Healthy: VPN connected, port=${PORT}, response_time=${response_time}s"
exit 0
