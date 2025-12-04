#!/bin/sh
# Gluetun healthcheck - verify VPN tunnel, connectivity, and port forwarding

set -e

MAX_LATENCY_MS=${MAX_LATENCY_MS:-5000}

now_ms() {
  echo $(( $(date +%s) * 1000 ))
}

if ! ip link show tun0 >/dev/null 2>&1; then
  echo "tun0 interface not found"
  exit 1
fi

START=$(now_ms)
if ! curl -sf --max-time 10 https://protonwire.p3.pm/status/json >/dev/null 2>&1; then
  echo "External connectivity failed"
  exit 1
fi
END=$(now_ms)

LATENCY=$((END - START))
if [ "$LATENCY" -gt "$MAX_LATENCY_MS" ]; then
  echo "VPN latency too high: ${LATENCY}ms (max ${MAX_LATENCY_MS}ms)"
  exit 1
fi

if [ ! -s /tmp/gluetun/forwarded_port ]; then
  echo "Port forwarding file missing or empty"
  exit 1
fi

PORT=$(cat /tmp/gluetun/forwarded_port 2>/dev/null || echo "")

if [ -z "$PORT" ]; then
  echo "Port forwarding data unavailable"
  exit 1
fi

echo "Healthy: latency=${LATENCY}ms, port=${PORT}"
exit 0
