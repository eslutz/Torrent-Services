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

**Deploy with guardrails:**

```bash
# 1. Configure environment
cp .env.example .env
# Set ProtonVPN credentials in .env
# Leave GLUETUN_CONTROL_APIKEY empty—bootstrap will auto-generate it
nano .env

# Environment file layout (top-to-bottom):
#   1) System configuration (PUID/PGID, TZ, DATA_DIR, SERVICE_USER, HOST_PROJECT_DIR)
#   2) VPN (WireGuard keys, server selection)
#   3) Gluetun control server auth (API key - auto-generated)
#   4) Torrent client & port sync (qBittorrent, Forwardarr)
#   5) *Arr services (Prowlarr, Sonarr, Radarr, Bazarr)
#   6) Subtitle providers (OpenSubtitles, Addic7ed)
#   7) Resource limits (optional) + example presets
#   8) Monitoring profile toggle

# 2. Start services (health checks and dependencies gate startup automatically)
docker compose up -d

# 3. Run Bootstrap Process (automates Gluetun auth, API key extraction, and service connections)
# See scripts/setup/README.md for more details
docker compose --profile bootstrap up

# 4. Verify VPN and port forwarding
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json
docker exec gluetun cat /tmp/gluetun/forwarded_port
docker logs forwardarr --tail 20

# 5. (Optional) Start monitoring exporters after bootstrap completes
# Start manually any time:
docker compose --profile monitoring up -d qbittorrent-exporter scraparr
```

### Healthchecks & Autoheal

- Every core container mounts `./scripts/healthchecks` and runs a dedicated script (e.g., `sonarr.sh`, `gluetun.sh`) that validates API responses, latency, and VPN/Tor prerequisites. Services with built-in health endpoints (like `torarr`) use native HTTP healthchecks instead.
- Gluetun healthcheck requires `GLUETUN_CONTROL_APIKEY` to be set in `.env` (auto-generated and populated by bootstrap on first run).
- Healthchecks run every 30 seconds with a 10–15 second timeout and fail fast if responses exceed 5 seconds, forcing Docker to flag the service as `unhealthy`.
- The Rust-based `autoheal` sidecar (`tmknight/docker-autoheal`) watches Docker health status via the socket, restarts unhealthy containers after the configured start delay, and persists JSON logs to a named volume for auditing.
- Inspect autoheal activity with `docker logs autoheal --tail 50`, follow the structured log file, and view per-container health with `docker ps --format "table {{.Names}}\t{{.Status}}"`.
- After running bootstrap, all healthchecks should pass. If gluetun fails, verify `GLUETUN_CONTROL_APIKEY` is set in `.env`: `grep GLUETUN_CONTROL_APIKEY .env`

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

### Step 2: Configure Authentication

**Automated Setup:**
The bootstrap script uses Playwright to automatically configure authentication for Prowlarr, Sonarr, Radarr, and Bazarr using the credentials in your `.env` file.

1. **Define credentials in `.env`:**
    Ensure you have set the following variables (defaults are provided in `.env.example`):
    - `SERVICE_USER` (used for all services)
    - `QBITTORRENT_PASSWORD`
    - `PROWLARR_PASSWORD`
    - `SONARR_PASSWORD`
    - `RADARR_PASSWORD`
    - `BAZARR_PASSWORD`

2. **Run the Bootstrap Process:**

    ```bash
    docker compose --profile bootstrap up
    ```

    The process will automatically:
    - Initialize authentication for all services.
    - Configure qBittorrent authentication.
    - Extract API keys from all services.
    - Configure inter-service connections.

> **Note:** If you have already manually configured authentication via the Web UI, the script will detect this and proceed to API key extraction.

### Step 3: Verify Automatic Port Forwarding

The `forwardarr` container automatically watches for port changes and updates qBittorrent instantly when they occur.

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

### Step 4: Manual Configuration (If Bootstrap Skipped)

> **Note:** The bootstrap process handles all of this automatically. Only follow these steps if you prefer manual configuration.

#### Configure Prowlarr Indexers

1. **Add Indexers in Prowlarr:**
   - Go to `http://localhost:9696`
   - Navigate to **Indexers** → **Add Indexer**
   - Search for and add your preferred indexers (e.g., 1337x, IPTorrents)
   - Configure credentials for private trackers if needed
   - **Test** and **Save** each indexer

2. **Connect Sonarr to Prowlarr:**
   - In Prowlarr, go to **Settings** → **Apps** → **Add Application**
   - Select **Sonarr**
   - Configure:
     - **Prowlarr Server:** `http://prowlarr:9696` (for Sonarr to reach Prowlarr)
     - **Sonarr Server:** `http://sonarr:8989` (for Prowlarr to reach Sonarr)
     - **API Key:** Get from Sonarr → Settings → General → API Key
   - Click **Test** → **Save**
   - Prowlarr will automatically sync all indexers to Sonarr

3. **Connect Radarr to Prowlarr:**
   - In Prowlarr, go to **Settings** → **Apps** → **Add Application**
   - Select **Radarr**
   - Configure:
     - **Prowlarr Server:** `http://prowlarr:9696`
     - **Radarr Server:** `http://radarr:7878`
     - **API Key:** Get from Radarr → Settings → General → API Key
   - Click **Test** → **Save**
   - Prowlarr will automatically sync all indexers to Radarr

#### Configure Download Client (qBittorrent)

Since qBittorrent runs inside Gluetun's network, access it via `gluetun:8080`

**Sonarr:**

1. Go to `http://localhost:8989`
2. Navigate to **Settings** → **Download Clients** → **Add** → **qBittorrent**
3. Configure:
   - **Name:** qBittorrent
   - **Host:** `gluetun`
   - **Port:** `8080`
   - **Username:** admin
   - **Password:** (your qBittorrent API password from .env: QBITTORRENT_PASSWORD)
   - **Category:** `tv` (recommended for organization)
4. Click **Test** → **Save**

**Radarr:**

1. Go to `http://localhost:7878`
2. Navigate to **Settings** → **Download Clients** → **Add** → **qBittorrent**
3. Configure:
   - **Name:** qBittorrent
   - **Host:** `gluetun`
   - **Port:** `8080`
   - **Username:** admin
   - **Password:** (your qBittorrent API password from .env: QBITTORRENT_PASSWORD)
   - **Category:** `movies` (recommended for organization)
4. Click **Test** → **Save**

#### Configure Bazarr with Sonarr and Radarr

> **Note**: The bootstrap script automatically configures Bazarr including Sonarr/Radarr connections, subtitle providers (Addic7ed, Podnapisi, OpenSubtitles), language profiles, and scoring settings. Manual configuration is only needed if customizing beyond the defaults in `scripts/setup/setup.config.json`.

**Connect Bazarr to Sonarr (TV Subtitles):**

1. Go to `http://localhost:6767`
2. Navigate to **Settings** → **Sonarr**
3. Click **Add New** and configure:
   - **Enabled:** ✅
   - **Name:** Sonarr
   - **Address:** `sonarr`
   - **Port:** `8989`
   - **Base URL:** (leave empty)
   - **API Key:** Get from Sonarr → Settings → General → API Key
   - **Download only monitored:** ✅ (recommended)
   - **Minimum Score:** `90` (adjust to preference)
   - **Use Sonarr Tags:** (optional - tag specific shows)
4. Click **Test** → **Save**

**Connect Bazarr to Radarr (Movie Subtitles):**

1. In Bazarr, navigate to **Settings** → **Radarr**
2. Click **Add New** and configure:
   - **Enabled:** ✅
   - **Name:** Radarr
   - **Address:** `radarr`
   - **Port:** `7878`
   - **Base URL:** (leave empty)
   - **API Key:** Get from Radarr → Settings → General → API Key
   - **Download only monitored:** ✅ (recommended)
   - **Minimum Score:** `90` (adjust to preference)
   - **Use Radarr Tags:** (optional - tag specific movies)
3. Click **Test** → **Save**

**Configure Languages in Bazarr (Required):**

1. Navigate to **Settings** → **Languages**
2. **Subtitles Language:**
   - Add **English** (or your preferred language)
   - This defines which subtitle languages Bazarr will search for
3. **Single Language:**
   - Leave **OFF** (most modern players like Plex/Jellyfin handle `.en.srt` filenames)
   - Only enable if your playback device can't handle language codes in filenames
4. **Languages Filter** (leave defaults):
   - **Language Equals:** Leave empty (only needed for treating languages as interchangeable)
   - **Embedded Tracks Language - Deep analyze media file:** **OFF** (faster, use ON only if files have inconsistent metadata)
   - **Treat unknown language embedded subtitles track as:** Leave as default or set to **English**
5. **Languages Profile** (create default profile):
   - Go to **Languages Profiles** section
   - Click **Add** to create a new profile:
     - **Name:** `English`
     - **Tag:** (optional) `english` or `eng-sub`
     - **Languages:** Click **Add Language** twice to add English two times:

       **First English entry (Normal subtitles):**
       - **Language:** English
       - **Subtitles Type:** **Normal or hearing-impaired** - full subtitles for all dialogue including foreign parts
       - **Search only when:** **Always** - search every time, upgrade low-quality subtitles (recommended)
       - **Must contain:** Leave empty
       - **Must not contain:** Leave empty

       **Second English entry (Forced subtitles):**
       - **Language:** English
       - **Subtitles Type:** **Forced (foreign part only)** - only foreign language parts, no regular dialogue subtitles
       - **Search only when:** **Always**
       - **Must contain:** Leave empty
       - **Must not contain:** Leave empty

     - This downloads both subtitle files: full subtitles + forced-only (for foreign parts)
     - Your media player will show both as separate tracks you can toggle
   - Click **Save**
6. **Tag-Based Automatic Language Profile Selection:**
   - Leave **OFF** (unless you use tags in Sonarr/Radarr for different language needs)
7. **Default Language Profiles for Newly Added Shows:**
   - **Series:** Select your **English** profile
   - **Movies:** Select your **English** profile
   - This ensures all new content automatically gets English subtitles
8. **Save** all settings

**Configure Subtitle Providers in Bazarr:**

1. Navigate to **Settings** → **Providers**
2. Enable subtitle providers (recommended free options):
   - **Addic7ed:** Requires free account at [addic7ed.com](https://www.addic7ed.com/) - excellent for TV shows
   - **Podnapisi:** No account needed - good general provider
   - **OpenSubtitles.com:** Requires free account at [opensubtitles.com](https://www.opensubtitles.com/) - large database
3. **Save** settings

**Sync Libraries:**

1. Navigate to **Series** (TV shows) and click **Update all series**
2. Navigate to **Movies** and click **Update all movies**
3. Bazarr will now automatically download subtitles for new and existing media

## How Automatic Port Forwarding Works

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
