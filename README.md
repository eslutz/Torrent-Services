# Media Automation Stack (Torrent Services)

[![CI Pipeline](https://github.com/eslutz/Torrent-Services/actions/workflows/ci.yml/badge.svg)](https://github.com/eslutz/Torrent-Services/actions/workflows/ci.yml)
[![Security Analysis](https://github.com/eslutz/Torrent-Services/actions/workflows/security.yml/badge.svg)](https://github.com/eslutz/Torrent-Services/actions/workflows/security.yml)

Automated media download and management using Docker with qBittorrent, Gluetun, Prowlarr, Sonarr, Radarr, Bazarr, and ProtonVPN port forwarding.

## Features

| Tool | Purpose | Website |
|------|---------|---------|
| **qBittorrent** | Torrent client | [qBittorrent](https://www.qbittorrent.org) |
| **Gluetun** | VPN client with ProtonVPN & port forwarding | [Gluetun](https://github.com/qdm12/gluetun) |
| **Prowlarr** | Indexer management | [Prowlarr](https://prowlarr.com/) |
| **Sonarr** | TV show management | [Sonarr](https://sonarr.tv/) |
| **Radarr** | Movie management | [Radarr](https://radarr.video/) |
| **Bazarr** | Subtitle management | [Bazarr](https://www.bazarr.media) |
| **Unpackerr** | Extracts completed downloads for *arr apps | [Unpackerr](https://github.com/Unpackerr/unpackerr) |
| **Tdarr** | Automated media transcoding (H.265/HEVC) | [Tdarr](https://tdarr.io/) |
| **Apprise** | Unified notification service (100+ platforms) | [Apprise](https://github.com/caronc/apprise) |
| **Overseerr** | Request management and media discovery | [Overseerr](https://overseerr.dev/) |
| **Torarr** | Optional SOCKS5 proxy for Tor-only indexers | [Torarr](https://github.com/eslutz/Torarr) |
| **Forwardarr** | Syncs Gluetun forwarded port into qBittorrent | [Forwardarr](https://github.com/eslutz/Forwardarr) |
| **Monitoring Exporters** | Prometheus metrics via Scraparr (*arr apps) + martabal/qbittorrent-exporter | [Scraparr](https://github.com/thecfu/scraparr) / [martabal/qbittorrent-exporter](https://github.com/martabal/qbittorrent-exporter) |

**VPN:** ProtonVPN with automatic port forwarding via Gluetun for optimal torrent performance and privacy.

**Resilience & observability highlights:**

- VPN-aware health checks keep qBittorrent offline until Gluetun verifies the tunnel, Tor proxy, and port-forward files.
- Dedicated `/scripts/healthchecks/*.sh` probes enforce latency thresholds and hit real APIs so containers only report healthy when they are responsive.
- Service dependencies wait for healthy upstream services (e.g., Sonarr/Radarr wait for Prowlarr).
- Autoheal container watches Docker health status and restarts stuck services automatically.
- Cgroup CPU/RAM limits, stop_grace_periods, and `init: true` guard the host from runaway containers.
- Hardened helpers: Forwardarr handles port sync with built-in health/metrics endpoints.
- Optional monitoring profile exposes native Prometheus metrics without touching production services.
- Resource budgets live in `.env`, so you can scale limits up/down without editing `docker-compose.yml`.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), ProtonVPN Plus subscription ([Sign up](https://protonvpn.com/))

### Option 1: Fresh Installation

For detailed step-by-step instructions, see [scripts/setup/README.md](scripts/setup/README.md).

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Set ProtonVPN credentials and service passwords

# 2. Start services
docker compose up -d

# 3. Configure services via web UI (one-time setup)
# - See [setup documentation](scripts/setup/README.md) for detailed configuration steps
# - Configure: Prowlarr, Sonarr, Radarr, Bazarr, qBittorrent

# 4. Create backup of your configuration
./scripts/utilities/backup_config.sh

# 5. Verify VPN and port forwarding
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json
docker exec gluetun cat /tmp/gluetun/forwarded_port
docker logs forwardarr --tail 20
```

### Option 2: Restore from Backup

If you have an existing backup:

```bash
# 1. Restore configuration
./scripts/utilities/restore_config.sh ./backups/20251222_143000

# 2. Complete manual UI restore steps (see output for instructions)
# - Sonarr: http://localhost:8989 → System → Backup → Restore
# - Radarr: http://localhost:7878 → System → Backup → Restore
# - Prowlarr: http://localhost:9696 → System → Backup → Restore
# - Bazarr: http://localhost:6767 → System → Backup → Restore

# 3. Verify all services are healthy
docker compose ps
```

**Total setup time:** ~5 minutes (automated restore + 4 manual UI clicks)

### Legacy Bootstrap Process

The programmatic setup scripts are still available in `scripts/setup_legacy/` but are **no longer the recommended approach**. The backup/restore method is simpler and more reliable.

If you still want to use the legacy bootstrap:
```bash
docker compose --profile bootstrap up
```

### Healthchecks & Autoheal

- Every core container mounts `./scripts/healthchecks` and runs a dedicated script (e.g., `sonarr.sh`, `gluetun.sh`) that validates API responses, latency, and VPN/Tor prerequisites. Services with built-in health endpoints (like `torarr`) use native HTTP healthchecks instead.
- Gluetun healthcheck requires `CONTROL_APIKEY` to be set in `.env` (auto-generated and populated by bootstrap on first run).
- Healthchecks run every 30 seconds with a 10–15 second timeout and fail fast if responses exceed 5 seconds, forcing Docker to flag the service as `unhealthy`.
- The Rust-based `autoheal` sidecar (`tmknight/docker-autoheal`) watches Docker health status via the socket, restarts unhealthy containers after the configured start delay, and persists JSON logs to a named volume for auditing.
- Inspect autoheal activity with `docker logs autoheal --tail 50`, follow the structured log file, and view per-container health with `docker ps --format "table {{.Names}}\t{{.Status}}"`.
- After running bootstrap, all healthchecks should pass. If gluetun fails, verify `CONTROL_APIKEY` is set in `.env`: `grep CONTROL_APIKEY .env`

### Monitoring Profile & Metrics

The docker compose stack ships with a lightweight Go qBittorrent exporter plus Scraparr (covering Sonarr/Radarr/Prowlarr/Bazarr) under the `monitoring` profile.

#### How the Monitoring Architecture Works

```txt
┌─────────────┐     scrape /metrics     ┌────────────┐     query      ┌─────────┐
│  Exporters  │ ◄────────────────────── │ Prometheus │ ◄───────────── │ Grafana │
│ (this stack)│                         │  (storage) │                │ (UI)    │
└─────────────┘                         └────────────┘                └─────────┘
      │                                       │                            │
 Expose current                         Store time-series           Visualize data
 metrics only                           data (history)              from Prometheus
```

**Understanding the components:**

1. **Exporters** (included here): Expose current metrics at a `/metrics` endpoint in Prometheus format. They **don't store data**—each scrape returns a snapshot of the current state.

2. **Prometheus** (not included): Scrapes exporter endpoints on a schedule (e.g., every 15s) and stores the time-series data. Without Prometheus, you only see current values—no history, no trends.

3. **Grafana** (not included): Queries Prometheus to visualize stored data. "Included dashboards" from exporters like Scraparr are **pre-built Grafana dashboard JSON files** you import into your Grafana instance—they're not standalone UIs.

**To get a complete monitoring solution**, you need all three components. This stack provides the exporters; Prometheus and Grafana typically run on a dedicated monitoring host (e.g., in your `network-services` stack).

#### Configuration

- The bootstrap process (`docker compose --profile bootstrap up`) reads API keys from each app and writes `SONARR_API_KEY`, `RADARR_API_KEY`, `PROWLARR_API_KEY`, and `BAZARR_API_KEY` into `.env`. Leave those values blank initially—the script will populate them for Scraparr.
- Set `ENABLE_MONITORING_PROFILE=true` in `.env` before running the bootstrap process to automatically start the exporters, or launch them manually with `docker compose --profile monitoring up -d ...` once keys exist.
- All exporter ports are bound to `127.0.0.1` to keep metrics private from the LAN. Point your Prometheus scrape config at the host loopback IP.

| Exporter | Endpoint | Notes |
|----------|----------|-------|
| qBittorrent | <http://127.0.0.1:8090/metrics> | `martabal/qbittorrent-exporter` with per-tracker stats enabled |
| Forwardarr | <http://127.0.0.1:9090/metrics> | Native metrics: current forwarded port, sync operations, qBit API call counts/errors, last sync timestamp |
| Torarr | <http://127.0.0.1:8085/metrics> | Native metrics: Tor bootstrap progress, circuit status, bytes read/written, external check results |
| Scraparr (*arr aggregate) | <http://127.0.0.1:7100/metrics> | Unified endpoint for Sonarr/Radarr/Prowlarr/Bazarr: queue sizes, calendar items, disk usage, health checks |

Prometheus scrape example (run from your monitoring host, adjust IP if remote):

```yaml
scrape_configs:
  - job_name: 'torrent-services'
    static_configs:
      - targets:
          - '127.0.0.1:8080'  # qBittorrent WebUI (optional, for up/down checks)
          - '127.0.0.1:8090'  # qBittorrent exporter (Prometheus metrics)
          - '127.0.0.1:9090'  # Forwardarr (port sync metrics)
          - '127.0.0.1:8085'  # Torarr (Tor proxy metrics)
          - '127.0.0.1:7100'  # Scraparr (Sonarr/Radarr/Prowlarr/Bazarr metrics)
          - '127.0.0.1:9696'  # Prowlarr (native /ping for up check, no /metrics)
          - '127.0.0.1:8989'  # Sonarr (native /ping for up check, no /metrics)
          - '127.0.0.1:7878'  # Radarr (native /ping for up check, no /metrics)
          - '127.0.0.1:6767'  # Bazarr (native /ping for up check, no /metrics)
```

> **Note:** The *arr apps (Prowlarr, Sonarr, Radarr, Bazarr) don't expose a `/metrics` endpoint—Scraparr aggregates their stats via API. Including them in targets is only useful for basic up/down probes (e.g., blackbox exporter or Prometheus `probe` module).

Stop the monitoring containers without impacting the main stack:

```bash
docker compose --profile monitoring down
```

## Git Hooks (Pre-commit)

This repo uses the cross-platform `pre-commit` framework to run linting and unit tests **only when staged code files change** (it skips docs-only commits).

One-time setup:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/pre-commit install
```

Optional convenience script (Unix-like shells):

```bash
./scripts/git/install_git_hooks.sh
```

## Directory Structure


```txt
torrent-services/
├── config/                 # Service configuration files
│   ├── gluetun/            # Gluetun VPN configuration
│   ├── qbittorrent/        # qbittorrent configuration
│   ├── prowlarr/           # Prowlarr configuration
│   ├── sonarr/             # Sonarr configuration
│   ├── radarr/             # Radarr configuration
│   └── bazarr/             # Bazarr configuration
├── media/                  # Media and downloads (or set DATA_DIR in .env)
├── docker-compose.yml      # Docker Compose configuration
├── .env                    # Environment variables (create from .env.example)
└── .env.example            # Example environment configuration
```

**Volume Mappings:**

- **Config directories** are mounted to `/config` in each container
- **Media directory** is mounted to `/media` in containers, providing a unified view of the data directory structure that allows all services to reference the same paths for media libraries and downloads
- `.env` holds ProtonVPN credentials, qBittorrent credentials, and (after running the bootstrap process) the API keys required for the monitoring exporters.
- Optional CPU/RAM limits are controlled through `.env` (see **Resource Limit Overrides** below) so machines with different sizes can share the same compose file.

### Resource Limit Overrides

- Each service’s `mem_limit`/`cpus` value references an environment variable with sane defaults (e.g., `SONARR_MEM_LIMIT=1g`, `TOR_PROXY_CPUS=0.25`).
- Adjust any combination in `.env` to right-size the stack for tiny hosts or beefy servers without editing YAML.
- Example: to halve qBittorrent’s CPU allowance and increase Gluetun memory, set

```bash
QBITTORRENT_CPUS="1.0"
GLUETUN_MEM_LIMIT="384m"
```

and re-run `docker compose up -d` to apply.

## ProtonVPN Setup Guide

### Step 1: Get ProtonVPN Credentials

1. **Sign up for ProtonVPN Plus** at [protonvpn.com](https://protonvpn.com/)
   - **Important:** Port forwarding requires Plus or higher tier (not available on free plan)

2. **Generate WireGuard Configuration:**
   - Log in to your ProtonVPN account
   - Go to **Account** → **WireGuard configuration**
   - **Select a P2P server** (marked with P2P icon - these support port forwarding)
     - Recommended countries: Netherlands, Iceland, Sweden, Switzerland, Singapore
   - Click **Create** to generate a configuration
   - Download the `.conf` file

3. **Extract Credentials:**
   Open the downloaded `.conf` file and find these values in the `[Interface]` section:

   ```ini
   [Interface]
   PrivateKey = ABC123...xyz  # Copy this
   Address = 10.2.0.2/32      # Copy this
   ```

4. **Add to `.env` file:**

   ```bash
   WIREGUARD_PRIVATE_KEY=ABC123...xyz
   WIREGUARD_ADDRESSES=10.2.0.2/32
   ```

### Step 2: Configure Services

See [scripts/setup/README.md](scripts/setup/README.md) for detailed configuration instructions for:
- ProtonVPN WireGuard setup
- Service authentication
- Prowlarr indexer configuration
- Sonarr/Radarr download client setup
- Bazarr subtitle provider configuration

### Step 3: Create Backup

Once configured, create a backup of your "known-good state":

```bash
./scripts/utilities/backup_config.sh
```

This backup can be restored on any host using the restore script.

### Verify Automatic Port Forwarding

```bash
# Check Gluetun's forwarded port
docker exec gluetun cat /tmp/gluetun/forwarded_port

# View port updater logs
docker logs forwardarr --tail 20

# Verify qBittorrent is connectable (check status bar at http://localhost:8080)
```

You should see logs like:

```bash
✓ Found forwarded port: 51820
🔄 Updating qBittorrent port from 6881 to 51820
✓ Successfully updated qBittorrent port to: 51820
```

**That's it!** The port will automatically update whenever Gluetun reconnects or restarts.

---

## Unpackerr - Automated Archive Extraction

Unpackerr automatically detects and extracts compressed downloads (RAR, ZIP, 7z, tar) from Sonarr and Radarr, then notifies them to import the extracted files.

### Features

- **Automatic extraction:** Monitors completed downloads for compressed files
- **Multi-format support:** RAR, ZIP, 7z, tar, gzip, bzip2
- **Password handling:** Attempts common passwords for protected archives
- **Cleanup:** Removes archives after successful extraction
- **Integration:** Works seamlessly with Sonarr and Radarr
- **Health monitoring:** Metrics endpoint for status checks

### Configuration

1. **Verify Integration:**
   The service is pre-configured with environment variables to connect to Sonarr and Radarr. No manual configuration needed.

2. **Monitor Extraction:**
   ```bash
   # View logs
   docker logs unpackerr --tail 50
   
   # Check metrics endpoint
   curl http://localhost:5656/metrics
   ```

3. **Customization (Optional):**
   Adjust settings in `.env`:
   - `UN_INTERVAL`: How often to scan for archives (default: 1h)
   - Resource limits via `UNPACKERR_MEM_LIMIT` and `UNPACKERR_CPUS`

### How It Works

1. Sonarr/Radarr downloads a torrent containing compressed files
2. qBittorrent completes the download
3. Sonarr/Radarr notify Unpackerr via webhook
4. Unpackerr extracts the archives in-place
5. Unpackerr notifies Sonarr/Radarr to import the extracted files
6. Original archives are removed after successful import

### Troubleshooting

**Extraction not happening:**
- Check Unpackerr logs: `docker logs unpackerr`
- Verify API keys in `.env` match Sonarr/Radarr
- Ensure proper file permissions on media directory

**Password-protected archives:**
- Unpackerr attempts common passwords automatically
- If extraction fails, check logs for password errors
- Consider adding custom passwords via environment variables

**Supported formats:**
- RAR (any version)
- ZIP
- 7z
- tar/tar.gz/tar.bz2
- gzip
- bzip2

---

## Tdarr - Automated Media Transcoding

Tdarr automatically transcodes media files to save storage space and ensure compatibility. It waits for torrents to complete and meet seeding requirements before transcoding.

### Features

- **In-place transcoding:** Replace original files with transcoded versions
- **H.265/HEVC encoding:** Significant space savings with minimal quality loss
- **English-only:** Keep only English audio and subtitle tracks by default
- **Torrent-aware:** Only processes files after qBittorrent confirms completion and seeding goals met
- **Distributed processing:** Server manages flows, nodes perform the work

### Configuration

1. **Access Tdarr Web UI:** <http://localhost:8265>

2. **Configure Libraries:**
   - Add your media paths (`/media` points to your `TORRENT_MEDIA_DIR`)
   - Set folder watch settings to monitor for new files
   - Enable in-place transcoding (cache files are temporary)

3. **Create Transcode Flows:**
   - **Output codec:** H.265 (HEVC) - set via `TDARR_OUTPUT_CODEC` env var
   - **Output container:** .m4v or .mp4 - set via `TDARR_OUTPUT_CONTAINER` env var
   - **Audio:** Keep only English tracks, remove others
   - **Subtitles:** Keep only English tracks, remove others
   - **Conditions:** Only process files in complete/seeded state

4. **Wait for Completion:**
   Tdarr depends on qBittorrent being healthy, ensuring files are fully downloaded before processing. For seeding requirements, configure flow conditions to check:
   - File age (e.g., only process files older than 7 days to allow seeding)
   - Or manually verify torrents meet seeding goals before adding to Tdarr library

### Environment Variables

See `.env.example` for configuration options:
- `TDARR_WEBUI_PORT` - Web interface (default: 8265)
- `TDARR_SERVER_PORT` - API/node communication (default: 8266)
- `TDARR_NODE_PORT` - Worker node port (default: 8267)
- `TDARR_OUTPUT_CODEC` - Default output codec (default: hevc)
- `TDARR_OUTPUT_CONTAINER` - Default container format (default: m4v)

### Horizontal Scaling for Better Performance

Tdarr supports running multiple node containers to significantly speed up transcoding. Use the helper scripts for automatic unique name generation, or manually use the compose file directly.

**Benefits:**
- **Linear performance scaling:** 2 nodes = 2x throughput, 3 nodes = 3x throughput
- **Automatic unique naming:** Each node gets a unique identifier
- **Better resource utilization:** Spread workload across CPU cores
- **Faster processing:** Reduce transcode queue times

**Quick Start (Recommended):**
```bash
# Start a new node with auto-generated unique name
./scripts/utilities/start_tdarr_node.sh

# Start with custom settings
./scripts/utilities/start_tdarr_node.sh --cpu-workers 4 --mem-limit 4g

# List all running nodes
./scripts/utilities/manage_tdarr_nodes.sh list

# Stop a specific node
./scripts/utilities/manage_tdarr_nodes.sh stop <unique-id>

# Stop all additional nodes
./scripts/utilities/manage_tdarr_nodes.sh stop-all
```

**Manual Method (Advanced):**
```bash
# Start node with manual project name
docker compose -f docker-compose.tdarr-node.yml --project-name tdarr-node-2 up -d

# Stop specific node
docker compose -f docker-compose.tdarr-node.yml --project-name tdarr-node-2 down

# View all running nodes
docker ps --filter "name=tdarr-node"
```

**Optional Customization:**
Set worker counts in `.env` (applies to all additional nodes):
```bash
TDARR_GPU_WORKERS="0"      # GPU workers (requires GPU passthrough)
TDARR_CPU_WORKERS="2"      # CPU workers per node
```

Or override per-node when using the script:
```bash
./scripts/utilities/start_tdarr_node.sh --cpu-workers 4 --gpu-workers 1 --cpus 4.0
```

**Recommendations:**
- Start with 1 node and add more if transcode queue grows
- Each node should have 1-2GB RAM per worker
- Monitor CPU usage - add nodes if CPU is consistently maxed out
- For GPU transcoding, use `--gpu-workers` flag or uncomment GPU passthrough in compose file

### Health Checks

- Tdarr server health is verified via API endpoint on port 8266
- If API is unavailable, falls back to web UI check on port 8265
- Both server and node containers are monitored for responsiveness

---

## Apprise - Unified Notifications

Apprise provides a unified REST API for sending notifications to 100+ services including Discord, Telegram, Email, Slack, Microsoft Teams, Signal, Home Assistant, and more—all fully self-hosted with no third-party cloud dependencies.

### Features

- **100+ notification services:** Discord, Telegram, email, Slack, Teams, Signal, Home Assistant, SMS, and more
- **Fully self-hosted:** No external registration or cloud dependencies required
- **REST API:** Simple HTTP interface for sending notifications
- **Web UI:** Configure and test notifications through browser
- **Persistent configs:** Save notification URLs with tags to `/config` volume for easy reuse across restarts (no need to re-enter credentials)
- **Attachments:** Send images and files with notifications

### Configuration

1. **Access Apprise:**
   - Web UI: <http://localhost:8000>
   - API endpoint: <http://localhost:8000/notify>

2. **Add Notification URLs:**
   Configure your notification services in `.env` or via the web UI. Examples:

   ```bash
   # Email
   APPRISE_EMAIL_URL="mailto://user:password@smtp.gmail.com:587?to=recipient@example.com"
   
   # Discord
   APPRISE_DISCORD_URL="discord://webhook_id/webhook_token"
   
   # Slack
   APPRISE_SLACK_URL="slack://bot_token/#channel"
   
   # Microsoft Teams
   APPRISE_TEAMS_URL="msteams://Webhook_ID/Webhook_Key/"
   
   # Signal (requires signal-cli-rest-api)
   APPRISE_SIGNAL_URL="signal://+15551234567@signal-api:8080"
   
   # Home Assistant
   APPRISE_HOMEASSISTANT_URL="hassios://hostname/access_token"
   
   # SMS via Twilio
   APPRISE_TWILIO_SMS_URL="twilio://account_sid:auth_token@from/to"
   
   # macOS Notifications (local macOS host only)
   APPRISE_MACOS_URL="macosx://"
   ```

   See `.env.example` for complete examples and 100+ more services.

3. **Create Persistent Configuration (Optional but Recommended):**
   
   Via Web UI:
   - Go to <http://localhost:8000>
   - Click "Configuration" → "Add New Configuration"
   - Enter a config name (e.g., "arr-alerts")
   - Add your notification URLs (one per line)
   - Add tags (e.g., "sonarr", "radarr", "critical")
   - Click "Save"

   Via API:
   ```bash
   # Create persistent config named "arr-alerts"
   curl -X POST http://localhost:8000/add/arr-alerts \
     -d "urls=discord://webhook_id/token&format=text&tag=arr-apps"
   ```

4. **Integrate with Sonarr:**
   - Go to Sonarr: <http://localhost:8989>
   - Navigate: **Settings** → **Connect** → **Add** → **Webhook**
   - Configure:
     - **Name:** Apprise Notifications
     - **On Grab:** ✓ (optional - when episode is sent to download client)
     - **On Import:** ✓ (recommended - when episode is imported)
     - **On Upgrade:** ✓ (optional - when episode is upgraded)
     - **On Rename:** (optional - usually not needed)
     - **On Series Add:** (optional - when new series added)
     - **On Series Delete:** ✓ (optional - when series removed)
     - **On Episode File Delete:** ✓ (optional - when files deleted)
     - **On Health Issue:** ✓ (recommended - for warnings/errors)
     - **On Health Restored:** ✓ (optional)
     - **On Application Update:** ✓ (optional)
     - **Tags:** (leave empty to apply to all, or specify series tags)
   - **URL:** Choose one option:
     - **Using persistent config:** `http://apprise:8000/notify/arr-alerts`
     - **Using direct URL:** `http://apprise:8000/notify/?urls=discord://webhook_id/token`
   - **Method:** POST
   - **Username:** (leave empty)
   - **Password:** (leave empty)
   - Click **Test** to verify connection
   - Click **Save**

5. **Integrate with Radarr:**
   - Go to Radarr: <http://localhost:7878>
   - Navigate: **Settings** → **Connect** → **Add** → **Webhook**
   - Configure (same as Sonarr but with movie-specific events):
     - **Name:** Apprise Notifications
     - **On Grab:** ✓ (optional)
     - **On Import:** ✓ (recommended)
     - **On Upgrade:** ✓ (optional)
     - **On Rename:** (optional)
     - **On Movie Added:** (optional)
     - **On Movie Delete:** ✓ (optional)
     - **On Movie File Delete:** ✓ (optional)
     - **On Health Issue:** ✓ (recommended)
     - **On Health Restored:** ✓ (optional)
     - **On Application Update:** ✓ (optional)
   - **URL:** `http://apprise:8000/notify/arr-alerts` (or direct URL)
   - **Method:** POST
   - Click **Test** and **Save**

6. **Integrate with Prowlarr:**
   - Go to Prowlarr: <http://localhost:9696>
   - Navigate: **Settings** → **Connect** → **Add** → **Webhook**
   - Configure:
     - **Name:** Apprise Notifications
     - **On Health Issue:** ✓ (recommended)
     - **On Health Restored:** ✓ (optional)
     - **On Application Update:** ✓ (optional)
   - **URL:** `http://apprise:8000/notify/arr-alerts` (or direct URL)
   - **Method:** POST
   - Click **Test** and **Save**

7. **Send Test Notification:**
   ```bash
   # Test with direct URL
   curl -X POST http://localhost:8000/notify \
     -d "urls=discord://webhook_id/token&body=Test notification from *arr apps"

   # Test with persistent config
   curl -X POST http://localhost:8000/notify/arr-alerts \
     -d "body=Test notification using saved config"
   ```

8. **Verify Notifications:**
   - Download a new episode/movie in Sonarr/Radarr
   - Check that notifications arrive in your configured services
   - Check Apprise logs if issues occur: `docker logs apprise`

### API Key Management

The `sync_api_keys.py` utility now focuses solely on Prowlarr key synchronization:
- **Syncs** Prowlarr API keys to Sonarr/Radarr indexers
- **Validates** all API key configurations

```bash
python3 scripts/utilities/sync_api_keys.py
```

### Health Checks

- Apprise health verified via `/health` endpoint
- Monitors for response time and service availability
- No authentication required for health checks

### Supported Services

Apprise supports 100+ notification services out of the box:
- **Chat:** Discord, Slack, Microsoft Teams, Telegram, Matrix, Mattermost
- **Email:** SMTP, Gmail, Outlook, SendGrid, Mailgun
- **SMS:** Twilio, ClickSend, AWS SNS, Vonage
- **Push:** Pushbullet, Pushover, Gotify, ntfy, Join
- **Voice:** AWS Polly, Google TTS
- **Smart Home:** Home Assistant, IFTTT, Zapier
- **Desktop:** macOS Notification Center (when run on macOS host)
- And many more! See [Apprise Wiki](https://github.com/caronc/apprise/wiki) for complete list.

---

## Overseerr - Request Management

Overseerr provides a sleek interface for users to request movies and TV shows, integrating with Plex/Emby/Jellyfin and automatically sending requests to Sonarr/Radarr.

### Features

- **User-friendly requests:** Simple interface for requesting media
- **Plex/Emby/Jellyfin integration:** Sync libraries and user permissions
- **Automatic processing:** Requests sent directly to Sonarr/Radarr
- **User management:** Control who can request and approve content
- **Mobile-friendly:** Responsive design for all devices

### Configuration

1. **Access Overseerr:**
   - Web UI: <http://localhost:5055>
   - Complete the setup wizard on first launch

2. **Connect Media Server:**
   - Add your Plex, Emby, or Jellyfin server
   - Configure library sync settings
   - Set user permissions

3. **Configure *arr Integration:**
   - Add Sonarr: `http://sonarr:8989` with API key from `.env`
   - Add Radarr: `http://radarr:7878` with API key from `.env`
   - Configure quality profiles and root folders

4. **User Settings:**
   - Enable/disable user registration
   - Set request limits per user
   - Configure approval workflows

### Health Checks

- Overseerr health verified via `/api/v1/status` endpoint
- Checks for valid version response
- Monitors response time (max 5s)
- Depends on Sonarr and Radarr being healthy

---

## Healthchecks & Autoheal

### The Process

1. **Gluetun starts** and connects to ProtonVPN P2P server
2. **ProtonVPN assigns** a forwarded port (changes on each connection)
3. **Gluetun saves** the port to `/tmp/gluetun/forwarded_port`
4. **Forwardarr watches** the file for changes using fsnotify
5. **Port automatically updates** in qBittorrent instantly when detected

### Forwardarr Port Sync

The Forwardarr container replaces the legacy script-based port updater:

- **Watches** Gluetun's forwarded port file for changes
- **Authenticates** with qBittorrent using credentials from `.env`
- **Updates** qBittorrent's listening port automatically
- **Exports** `/metrics`, `/health`, and `/ready` on port `9090` (bound to localhost)

### Forwardarr Configuration

Refer to [`.env.example`](.env.example) for optional Forwardarr tuning (`FORWARDARR_SYNC_INTERVAL`, `FORWARDARR_LOG_LEVEL`). Defaults work for most setups.

### Monitoring

```bash
# Live monitoring
docker logs -f forwardarr

# Last 20 lines
docker logs forwardarr --tail 20

# Health / readiness (inside host)
curl -sf http://127.0.0.1:9090/ready
curl -sf http://127.0.0.1:9090/health
```

**Access Services:**

| Service | URL | Local Domain | Network Access | Purpose |
|---------|-----|--------------|----------------|---------|
| qBittorrent | <http://localhost:8080> | <http://qbittorrent.home.arpa:8080> | <http://192.168.1.254:8080> | Torrents |
| Sonarr | <http://localhost:8989> | <http://sonarr.home.arpa:8989> | <http://192.168.1.254:8989> | TV shows |
| Radarr | <http://localhost:7878> | <http://radarr.home.arpa:7878> | <http://192.168.1.254:7878> | Movies |
| Prowlarr | <http://localhost:9696> | <http://prowlarr.home.arpa:9696> | <http://192.168.1.254:9696> | Indexers |
| Bazarr | <http://localhost:6767> | <http://bazarr.home.arpa:6767> | <http://192.168.1.254:6767> | Subtitles |
| Unpackerr | <http://localhost:5656> | <http://unpackerr.home.arpa:5656> | <http://192.168.1.254:5656> | Extract archives |
| Tdarr | <http://localhost:8265> | <http://tdarr.home.arpa:8265> | <http://192.168.1.254:8265> | Transcoding |
| Apprise | <http://localhost:8000> | <http://apprise.home.arpa:8000> | <http://192.168.1.254:8000> | Notifications |
| Overseerr | <http://localhost:5055> | <http://overseerr.home.arpa:5055> | <http://192.168.1.254:5055> | Requests |

**Addressing Guide:**

- **localhost** - Access from the same machine running Docker
- **home.arpa domains** - Network access after adding DNS records to Pi-hole (see [Network Integration](../docs/torrent-services/network-integration.md))
- **Network Access (192.168.1.254:port)** - Direct IP access from any device on your home network
- **service:port** - Inter-container communication (used in service configuration)

**How to Access from Other Computers:**

All services are accessible over your home network using the Network Access URLs above.

1. **Find the server IP:** Run `ifconfig | grep "inet " | grep -v 127.0.0.1` on the server to get its IP (currently: `192.168.1.254`)
2. **Access via browser:** Use `http://<SERVER_IP>:<PORT>` from any device on your network
3. **Bookmark for convenience:** Save the URLs in your browser

**For Inter-container Communication:**

When configuring services to talk to each other:

- **qBittorrent:** `gluetun:8080` (qBittorrent shares Gluetun's network)
- **Other services:** Use container name (e.g., `prowlarr:9696`, `sonarr:8989`)

**Authentication:** Each service uses Forms-based authentication. The `SERVICE_USER` and `QBITTORRENT_PASSWORD` in `.env` are used for API communication between Sonarr/Radarr and qBittorrent.

**qBittorrent temporary password:** `docker logs qbittorrent 2>&1 | grep "temporary password"`

## Documentation

### Internal Docs

- **[Setup & Bootstrap](./scripts/setup/README.md)** - Automated service configuration and inter-service connections
- **[Setup Scripts](./scripts/setup/README.md)** - Detailed documentation for the Python setup scripts
- **[Healthcheck](../docs/torrent-services/healthcheck.md)** - Container health monitoring and autoheal system
- **[Monitoring](../docs/torrent-services/monitoring.md)** - Prometheus metrics exporters setup

### Network Integration Docs

- **[Initial Setup](../docs/torrent-services/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-services/vpn-guide.md)** - VPN setup and troubleshooting
- **[Network Integration](../docs/torrent-services/network-integration.md)** - Home network architecture integration
- **[Maintenance](../docs/torrent-services/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-services/architecture-overview.md)** - Technical overview

## Common Commands

```bash
# Service Management
docker compose up -d                              # Start services
docker compose down                               # Stop all
docker compose restart <service>                  # Restart specific service
docker compose --profile monitoring up -d         # Start Prometheus exporters
docker compose --profile monitoring down          # Stop Prometheus exporters
docker compose logs -f <service>                  # View logs (follow mode)

# VPN Testing
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json  # Check VPN connection
docker exec gluetun cat /tmp/gluetun/forwarded_port                  # Get forwarded port
./scripts/vpn-speedtest.sh                                           # Run speed test & VPN check

# Port Forwarding
docker exec gluetun cat /tmp/gluetun/forwarded_port  # Check current forwarded port
docker logs forwardarr --tail 20                     # View port updater logs
docker logs -f forwardarr                            # Live monitoring of port updates

# Troubleshooting
docker compose ps                                 # Check container status
docker logs qbittorrent 2>&1 | grep "temporary password"  # Get qBittorrent temp password
docker logs gluetun | grep -i "port forward"     # Check port forwarding logs
```

## Troubleshooting

### Port Forwarding Not Working

1. **Verify P2P Server:**

   ```bash
   docker logs gluetun | grep -i "country"
   ```

   Ensure you're connected to a P2P-enabled country (Netherlands, Iceland, Sweden, Switzerland, Singapore)

2. **Check Forwarded Port:**

   ```bash
   docker exec gluetun cat /tmp/gluetun/forwarded_port
   ```

   If empty, restart Gluetun: `docker compose restart gluetun && sleep 30`

3. **Check port updater:**

   ```bash
   docker logs forwardarr --tail 20
   curl -sf http://127.0.0.1:9090/ready
   ```

   Look for successful updates or error messages

4. **Verify Connectivity:**
   - In qBittorrent, check status bar (bottom of page)
   - Should show connectable icon (green arrow/checkmark)
   - May take 1-2 minutes after port change

### qBittorrent Shows "Unconnectable"

1. **Check port updater is running:**

   ```bash
   docker ps | grep forwardarr
   docker logs forwardarr --tail 20
   curl -sf http://127.0.0.1:9090/ready
   ```

2. **Verify QBITTORRENT_PASSWORD is set in .env:**

   ```bash
   grep QBITTORRENT_PASSWORD .env
   ```

   If not set, add it and restart (QBITTORRENT_PASSWORD is used for API communication):

   ```bash
   echo "QBITTORRENT_PASSWORD=your_api_password" >> .env
   docker compose restart forwardarr
   ```

3. **Restart services:**

   ```bash
   docker compose restart qbittorrent forwardarr
   sleep 30
   ```

4. **Wait 2-3 minutes** for ProtonVPN to propagate the port forward

5. **Verify port was set correctly:**

   ```bash
   # Check Gluetun's forwarded port
   docker exec gluetun cat /tmp/gluetun/forwarded_port

   # Verify script output showed successful update
   ```

6. **Try adding a torrent** with many seeds to test

### Sonarr/Radarr Can't Connect to qBittorrent

1. Verify hostname is `gluetun` not `qbittorrent`
2. Verify port is `8080`
3. Test connection: `docker exec sonarr curl http://gluetun:8080`

### Advanced Torrent Troubleshooting

For issues with specific torrents (stalled, error state, path issues), use the included Python troubleshooting scripts.
See the **[Troubleshooting Documentation](./scripts/troubleshooting/TROUBLESHOOTING.md)** for full details.

## Security

- Never commit `.env` (contains ProtonVPN credentials - excluded via `.gitignore`)
- VPN kill-switch enabled: if VPN drops, qBittorrent loses internet access (no IP leak)
- Port forwarding managed automatically by ProtonVPN
- All torrent traffic routed through ProtonVPN tunnel
- Services accessible on local network (consider firewall rules if needed)
