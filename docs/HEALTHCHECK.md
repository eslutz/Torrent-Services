# Healthcheck Architecture

This document describes the healthcheck system that monitors container health and enables automatic recovery from degraded states.

## Overview

The torrent services stack uses **external healthcheck scripts** instead of inline YAML commands. Each service has a dedicated script in `scripts/healthchecks/` that validates:

- API responsiveness (not just port availability)
- Response time thresholds (slow = unhealthy)
- Service-specific prerequisites (VPN tunnel, Tor circuit, etc.)

When a service becomes unhealthy, the **autoheal** sidecar automatically restarts it.

## Architecture

```txt
┌─────────────────────────────────────────────────────────────────┐
│                    Healthcheck Flow                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐     healthcheck      ┌────────────┐
│  Container  │ ◄─────────────────── │   Docker   │
│  (service)  │     every 30s        │   Engine   │
└─────────────┘                      └────────────┘
      │                                    │
      │ runs script                        │ reports status
      ▼                                    ▼
┌─────────────┐                      ┌────────────┐
│  /scripts/  │                      │  autoheal  │
│  *.sh       │                      │  container │
└─────────────┘                      └────────────┘
      │                                    │
      │ validates API                      │ restarts if
      │ + latency                          │ unhealthy
      ▼                                    ▼
  exit 0/1                           docker restart
```

## Design Principles

1. **Deep checks over shallow checks**: Verify actual API functionality, not just port availability
2. **Response time matters**: Slow responses (>5s) indicate degraded state
3. **Fail fast, recover fast**: Short timeouts with reasonable retries
4. **External scripts**: Maintainable, testable, separate from YAML
5. **Automatic recovery**: Autoheal restarts unhealthy containers

## Scripts Directory

All healthcheck scripts are in `scripts/healthchecks/`:

```txt
scripts/healthchecks/
├── gluetun.sh       # VPN tunnel + connectivity + port forwarding
├── qbittorrent.sh   # API version endpoint with latency check
├── prowlarr.sh      # /ping endpoint with latency check
├── sonarr.sh        # /ping endpoint with latency check
├── radarr.sh        # /ping endpoint with latency check
├── bazarr.sh        # /ping endpoint with latency check
└── tor-proxy.sh     # SOCKS port + Tor circuit verification
```

## Healthcheck Configuration

### Timing Parameters

Each service uses these Docker healthcheck settings:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `interval` | 30s | Time between health checks |
| `timeout` | 10-15s | Max time for check to complete |
| `retries` | 3 | Failures before marking unhealthy |
| `start_period` | 60s | Grace period after container start |

### Response Time Thresholds

All services use a 5-second latency threshold (`MAX_LATENCY_MS=5000`). If API response exceeds this, the check fails.

| Condition | Health Status |
|-----------|---------------|
| Response < 5s | ✅ Healthy |
| Response ≥ 5s | ❌ Unhealthy (too slow) |
| No response | ❌ Unhealthy (timeout) |
| Wrong response | ❌ Unhealthy (error) |

## Service-Specific Checks

### Gluetun (VPN Client)

**Script**: `scripts/healthchecks/gluetun.sh`

**Checks**:

1. `tun0` interface exists (VPN tunnel is up)
2. External connectivity via ProtonVPN status endpoint
3. Response latency within threshold
4. Port forwarding file exists and contains valid port

```bash
# What it validates
ip link show tun0                           # VPN tunnel exists
curl https://protonwire.p3.pm/status/json   # External connectivity
cat /tmp/gluetun/forwarded_port             # Port forwarding active
```

### qBittorrent

**Script**: `scripts/healthchecks/qbittorrent.sh`

**Checks**:

1. API version endpoint responds
2. Response contains valid data
3. Response latency within threshold

```bash
# What it validates
curl http://localhost:8080/api/v2/app/version
```

### Prowlarr / Sonarr / Radarr / Bazarr

**Script**: `scripts/healthchecks/{service}.sh`

**Checks**:

When API keys are available (after running `bootstrap.sh`):

1. `/api/v*/health` endpoint responds with authentication
2. Response contains no errors or warnings
3. Response latency within threshold

When API keys are not available (initial startup):

1. `/ping` endpoint responds (fallback)
2. Response is not empty
3. Response latency within threshold

```bash
# What each validates (with API key)
curl -H "X-Api-Key: $API_KEY" http://localhost:9696/api/v1/health  # Prowlarr
curl -H "X-Api-Key: $API_KEY" http://localhost:8989/api/v3/health  # Sonarr
curl -H "X-Api-Key: $API_KEY" http://localhost:7878/api/v3/health  # Radarr
curl -H "X-Api-Key: $API_KEY" http://localhost:6767/api/system/health  # Bazarr
```

> **Note**: The scripts automatically use the deeper `/api/v*/health` endpoints when API keys are provided via environment variables. These endpoints check database status, disk space, service integrations, and more. If API keys are not available, the scripts fall back to the basic `/ping` endpoint.

### Tor Proxy

**Script**: `scripts/healthchecks/tor-proxy.sh`

**Checks**:

1. SOCKS port 9050 is listening
2. Tor circuit is functional (request through Tor succeeds)

```bash
# What it validates
nc -z localhost 9050                                    # Port available
curl --socks5-hostname localhost:9050 https://check.torproject.org/api/ip  # Tor works
```

## Autoheal Container

The `autoheal` container monitors Docker health status and automatically restarts unhealthy containers.

**Image**: `tmknight88/docker-autoheal:latest` (Rust-based, actively maintained)

### Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `AUTOHEAL_MONITOR_ALL` | `true` | Monitor all containers |
| `AUTOHEAL_INTERVAL` | `30` | Seconds between checks |
| `AUTOHEAL_START_DELAY` | `300` | Seconds to wait before monitoring new containers |
| `AUTOHEAL_STOP_TIMEOUT` | `30` | Seconds for graceful shutdown |
| `AUTOHEAL_LOG_PERSIST` | `true` | Write JSON logs to file |

### Log Location

Autoheal logs are written to `logs/autoheal.json`:

```bash
# View recent autoheal activity
cat logs/autoheal.json | jq -s '.[-10:]'

# Or via Docker logs
docker logs autoheal --tail 50
```

### Excluding Containers

To exclude a container from autoheal monitoring, add a label:

```yaml
labels:
  - "autoheal=false"
```

## Monitoring Health Status

### Quick Status Check

```bash
# All containers with health status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Detailed Health Info

```bash
# Detailed health for specific container
docker inspect --format='{{json .State.Health}}' sonarr | jq

# Last healthcheck output
docker inspect --format='{{.State.Health.Log}}' sonarr | jq '.[-1]'
```

### Watch in Real-Time

```bash
# Refresh every 5 seconds
watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}"'
```

## Testing Healthchecks

### Test Script Syntax

```bash
# Verify all scripts have valid syntax
for script in scripts/healthchecks/*.sh; do
    sh -n "$script" && echo "$script: OK"
done
```

### Simulate Failure

```bash
# Simulate Gluetun VPN failure
docker exec gluetun ip link set tun0 down
# Watch for healthcheck failure
watch docker ps --format "table {{.Names}}\t{{.Status}}"

# Simulate Sonarr database issue
docker exec sonarr mv /config/sonarr.db /config/sonarr.db.bak
# Wait for healthcheck to fail, then restore
docker exec sonarr mv /config/sonarr.db.bak /config/sonarr.db
```

## Troubleshooting

### Container Stuck "Starting"

If a container stays in "starting" health status too long:

1. Check the `start_period` value (default 60s)
2. Verify the service has fully initialized
3. Check container logs for startup errors:

   ```bash
   docker compose logs <service> --tail 100
   ```

### False "Unhealthy" Status

If a container keeps going unhealthy incorrectly:

1. Run the healthcheck manually:

   ```bash
   docker exec <container> /scripts/<service>.sh
   ```

2. Check if latency is consistently high:

   ```bash
   # Run multiple times
   for i in {1..5}; do
     docker exec sonarr /scripts/sonarr.sh
     sleep 2
   done
   ```

3. Consider increasing `MAX_LATENCY_MS` if network is slow

### Autoheal Not Restarting Containers

1. Check autoheal is running:

   ```bash
   docker ps | grep autoheal
   ```

2. Check autoheal logs:

   ```bash
   docker logs autoheal --tail 50
   ```

3. Verify container doesn't have `autoheal=false` label:

   ```bash
   docker inspect --format='{{.Config.Labels}}' <container>
   ```

### Frequent Restarts (Flapping)

If a container keeps restarting repeatedly:

1. Check autoheal logs for restart count
2. Investigate root cause in service logs
3. Consider temporarily excluding from autoheal:

   ```bash
   docker stop autoheal  # Disable auto-restart
   # Debug the issue
   docker start autoheal  # Re-enable
   ```

## Customization

### Adjusting Latency Threshold

Set via environment variable in healthcheck script:

```bash
MAX_LATENCY_MS=10000  # 10 seconds instead of 5
```

Or modify the script directly in `scripts/healthchecks/`.

### Changing Check Interval

Edit `docker-compose.yml` for the specific service:

```yaml
healthcheck:
  test: ["/scripts/sonarr.sh"]
  interval: 60s  # Changed from 30s
  timeout: 15s
  retries: 3
  start_period: 120s
```

### Adding Custom Checks

To add deeper validation (e.g., database queries):

1. Edit the relevant script in `scripts/healthchecks/`
2. Add additional validation logic
3. Ensure the script exits 0 (healthy) or 1 (unhealthy)

## References

- [Docker Healthcheck Documentation](https://docs.docker.com/engine/reference/builder/#healthcheck)
- [tmknight/docker-autoheal](https://github.com/tmknight/docker-autoheal)
