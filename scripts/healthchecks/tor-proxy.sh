#!/bin/sh
# Tor proxy healthcheck - verify Tor connectivity
#
# Validates:
#  - SOCKS5 proxy port is listening
#  - Tor is actually routing traffic through the network
#  - Can establish circuits to Tor network
#  - Response from Tor Project API confirms "IsTor":true
#  - Response time under 15 seconds
#
# Catches:
#  ❌ SOCKS port not listening
#  ❌ Tor daemon running but not connected to network
#  ❌ Circuit building failures
#  ❌ Network connectivity problems
#  ❌ Configuration errors preventing Tor connections
#  ❌ Tor consensus/directory issues

set -e

SOCKS_HOST=${SOCKS_HOST:-127.0.0.1}
SOCKS_PORT=${SOCKS_PORT:-9050}

# First check if SOCKS port is listening
if ! nc -z -w 1 "$SOCKS_HOST" "$SOCKS_PORT" >/dev/null 2>&1; then
  echo "SOCKS port ${SOCKS_PORT} not listening"
  exit 1
fi

# Verify Tor is actually routing traffic through the network
start_time=$(date +%s)
# Reduced timeout to 10s to fail faster if stalled
response=$(curl --silent --socks5-hostname "$SOCKS_HOST:$SOCKS_PORT" --max-time 10 https://check.torproject.org/api/ip 2>&1)
end_time=$(date +%s)
response_time=$((end_time - start_time))

# Check if response contains "IsTor":true
if ! echo "$response" | grep -q '"IsTor":true'; then
  echo "Tor connectivity check failed: $response"
  exit 1
fi

echo "Healthy: Tor network connected, response_time=${response_time}s"
exit 0
