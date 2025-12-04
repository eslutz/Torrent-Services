# Media Automation Stack (Torrent Services)

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
| **Tor Proxy** | Optional SOCKS5 proxy for Tor-only indexers | [torproxy](https://hub.docker.com/r/dperson/torproxy) |
| **Monitoring Exporters** | Prometheus metrics for qBittorrent/Sonarr/Radarr/Prowlarr | [Exportarr](https://github.com/onedr0p/exportarr) |

**VPN:** ProtonVPN with automatic port forwarding via Gluetun for optimal torrent performance and privacy.

**Resilience & observability highlights:**

- VPN-aware health checks keep qBittorrent offline until Gluetun verifies the tunnel, Tor proxy, and port-forward files.
- Service dependencies wait for healthy upstream services (e.g., Sonarr/Radarr wait for Prowlarr).
- Cgroup CPU/RAM limits, stop_grace_periods, and `init: true` guard the host from runaway containers.
- Hardened helpers: qbit-port-sync now runs read-only with tmpfs scratch space and detailed status health checks.
- Optional monitoring profile exposes native Prometheus metrics without touching production services.
- Resource budgets live in `.env`, so you can scale limits up/down without editing `docker-compose.yml`.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), ProtonVPN Plus subscription ([Sign up](https://protonvpn.com/))

**Deploy with guardrails:**

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Set ProtonVPN credentials, qBittorrent password, and optional ENABLE_MONITORING_PROFILE

# 2. Start services (health checks and dependencies gate startup automatically)
docker compose up -d

# 3. Run Bootstrap Script (automates auth, connections, and saves API keys to .env)
./scripts/bootstrap.sh

# 4. Verify VPN and port forwarding
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json
docker exec gluetun cat /tmp/gluetun/forwarded_port
docker logs qbit-port-sync --tail 20

# 5. (Optional) Start monitoring exporters after API keys exist
# Option A: set ENABLE_MONITORING_PROFILE=true before running bootstrap (auto-start)
# Option B: start manually any time:
docker compose --profile monitoring up -d qbittorrent-exporter sonarr-exporter radarr-exporter prowlarr-exporter
```

### Monitoring Profile & Metrics

- The docker compose stack ships with Prometheus exporters for qBittorrent, Sonarr, Radarr, and Prowlarr under the `monitoring` profile.
- `./scripts/bootstrap.sh` now reads API keys from each app and writes `SONARR_API_KEY`, `RADARR_API_KEY`, `PROWLARR_API_KEY`, and `BAZARR_API_KEY` into `.env`. Leave those values blank initially—the script will populate them.
- Set `ENABLE_MONITORING_PROFILE=true` in `.env` before running the bootstrap script to automatically start the exporters, or launch them manually with `docker compose --profile monitoring up -d ...` once keys exist.
- All exporter ports are bound to `127.0.0.1` to keep metrics private from the LAN. Point your Prometheus scrape config at the host loopback IP.

| Exporter | Endpoint | Notes |
|----------|----------|-------|
| qBittorrent | <http://127.0.0.1:9352/metrics> | `eshogu/qbittorrent-exporter` (requires QBIT_USER/PASS) |
| Sonarr | <http://127.0.0.1:9707/metrics> | `exportarr` profile `sonarr` |
| Radarr | <http://127.0.0.1:9708/metrics> | `exportarr` profile `radarr` |
| Prowlarr | <http://127.0.0.1:9709/metrics> | `exportarr` profile `prowlarr` |

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
- `.env` holds ProtonVPN credentials, qBittorrent credentials, and (after running `./scripts/bootstrap.sh`) the API keys required for the monitoring exporters.
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

### Step 2: Configure Authentication & Connections

The `bootstrap.sh` script automatically:

1. Sets up authentication for all services using credentials from `.env`
2. Connects Prowlarr, Sonarr, Radarr, and qBittorrent together
3. Configures indexers and subtitle providers

Simply run:

```bash
./scripts/bootstrap.sh
```

### Step 3: Verify Automatic Port Forwarding

The `qbit-port-sync` container automatically watches for port changes and updates qBittorrent instantly when they occur.

```bash
# Check Gluetun's forwarded port
docker exec gluetun cat /tmp/gluetun/forwarded_port

# View port updater logs
docker logs qbit-port-sync --tail 20

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

> **Note:** The `bootstrap.sh` script handles all of this automatically. Only follow these steps if you prefer manual configuration.

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
   - **Username:** `admin` (or your configured username)
   - **Password:** (your qBittorrent password)
   - **Category:** `tv` (recommended for organization)
4. Click **Test** → **Save**

**Radarr:**

1. Go to `http://localhost:7878`
2. Navigate to **Settings** → **Download Clients** → **Add** → **qBittorrent**
3. Configure:
   - **Name:** qBittorrent
   - **Host:** `gluetun`
   - **Port:** `8080`
   - **Username:** `admin` (or your configured username)
   - **Password:** (your qBittorrent password)
   - **Category:** `movies` (recommended for organization)
4. Click **Test** → **Save**

#### Configure Bazarr with Sonarr and Radarr

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
4. **port-updater watches** the file for changes using inotify
5. **Port automatically updates** in qBittorrent instantly when detected

### The qbit-port-sync Container

A lightweight Alpine Linux container runs alongside your stack:

- **Watches** Gluetun's forwarded port file for changes using inotify
- **Responds instantly** when the port changes
- **Authenticates** with qBittorrent using credentials from `.env`
- **Updates** qBittorrent's listening port automatically
- **Logs** all port changes for monitoring

### Configuration

Refer to [`.env.example`](.env.example) for all configuration options including credentials.

### Monitoring

View the port updater logs:

```bash
# Live monitoring
docker logs -f qbit-port-sync

# Last 20 lines
docker logs qbit-port-sync --tail 20
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

**qBittorrent password:** `docker logs qbittorrent 2>&1 | grep "temporary password"`

## Documentation

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
./vpn-speedtest.sh                                                # Run speed test & VPN check

# Port Forwarding
docker exec gluetun cat /tmp/gluetun/forwarded_port  # Check current forwarded port
docker logs qbit-port-sync --tail 20               # View port updater logs
docker logs -f qbit-port-sync                      # Live monitoring of port updates

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
   docker logs qbit-port-sync --tail 20
   ```

   Look for successful updates or error messages

4. **Verify Connectivity:**
   - In qBittorrent, check status bar (bottom of page)
   - Should show connectable icon (green arrow/checkmark)
   - May take 1-2 minutes after port change

### qBittorrent Shows "Unconnectable"

1. **Check port updater is running:**

   ```bash
   docker ps | grep qbit-port-sync
   docker logs qbit-port-sync --tail 20
   ```

2. **Verify QBIT_PASS is set in .env:**

   ```bash
   grep QBIT_PASS .env
   ```

   If not set, add it and restart:

   ```bash
   echo "QBIT_PASS=your_password" >> .env
   docker compose restart qbit-port-sync
   ```

3. **Restart services:**

   ```bash
   docker compose restart qbittorrent qbit-port-sync
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

## Security

- Never commit `.env` (contains ProtonVPN credentials - excluded via `.gitignore`)
- VPN kill-switch enabled: if VPN drops, qBittorrent loses internet access (no IP leak)
- Port forwarding managed automatically by ProtonVPN
- All torrent traffic routed through ProtonVPN tunnel
- Services accessible on local network (consider firewall rules if needed)
