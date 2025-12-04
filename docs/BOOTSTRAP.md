# Automated Service Bootstrap

This document describes the bootstrap system that automatically configures inter-service connections when deploying the torrent stack.

## Overview

The bootstrap system uses a **zero config files in Git** approach. Applications auto-generate their configurations on first boot, and the `bootstrap.sh` script uses their APIs to:

1. Extract auto-generated API keys from config files
2. Save API keys to `.env` for persistence and monitoring exporter use
3. Configure all inter-service connections
4. Set up indexers and download clients

This ensures:

- No secrets are ever committed to Git
- Each deployment has unique, secure API keys
- Configuration is reproducible and automated

## Architecture

```txt
┌─────────────────────────────────────────────────────────────────┐
│                     First-Time Setup Flow                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. docker compose up -d                                        │
│     - Containers start with empty config directories            │
│     - Each app auto-generates its own API key                   │
│     - Apps initialize with default settings                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. ./scripts/bootstrap.sh                                      │
│     - Waits for all services to be healthy                      │
│     - Reads API keys from each app's config file                │
│     - Saves API keys to .env for monitoring exporters           │
│     - Configures Prowlarr → Sonarr/Radarr apps                  │
│     - Configures Sonarr/Radarr → qBittorrent download client    │
│     - Configures Bazarr → Sonarr/Radarr connections             │
│     - Adds indexers to Prowlarr                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Stack is fully operational                                  │
│     - All services connected and authenticated                  │
│     - Indexers synced to Sonarr/Radarr                          │
│     - Ready to use                                              │
└─────────────────────────────────────────────────────────────────┘
```

## What Gets Configured

### Authentication

The bootstrap script enables Forms authentication on all services using credentials from `.env`:

| Service | Action | Credentials Source |
|---------|--------|-------------------|
| qBittorrent | Updates default/temp password | `QBIT_USER` / `QBIT_PASS` |
| Sonarr | Enables Forms Auth | `SONARR_USER` / `SONARR_PASS` |
| Radarr | Enables Forms Auth | `RADARR_USER` / `RADARR_PASS` |
| Prowlarr | Enables Forms Auth | `PROWLARR_USER` / `PROWLARR_PASS` |
| Bazarr | Enables Forms Auth | `BAZARR_USER` / `BAZARR_PASS` |

### API Key Extraction

API keys are read from each app's config file and saved to `.env`:

| Service | Config File | Saved To |
|---------|-------------|----------|
| Sonarr | `config/sonarr/config.xml` | `SONARR_API_KEY` |
| Radarr | `config/radarr/config.xml` | `RADARR_API_KEY` |
| Prowlarr | `config/prowlarr/config.xml` | `PROWLARR_API_KEY` |
| Bazarr | `config/bazarr/config/config.yaml` | `BAZARR_API_KEY` |

These saved API keys are used by:

- **Prowlarr** to connect to Sonarr and Radarr
- **Bazarr** to connect to Sonarr and Radarr
- **Monitoring exporters** (Scraparr) when the monitoring profile is enabled

### Service Connections

| Connection | Method | Data Source |
|------------|--------|-------------|
| Prowlarr → Sonarr | POST `/api/v1/applications` | API key from Sonarr config |
| Prowlarr → Radarr | POST `/api/v1/applications` | API key from Radarr config |
| Sonarr → qBittorrent | POST `/api/v3/downloadclient` | Credentials from `.env` |
| Radarr → qBittorrent | POST `/api/v3/downloadclient` | Credentials from `.env` |
| Bazarr → Sonarr | PATCH `/api/system/settings` | API key from Sonarr config |
| Bazarr → Radarr | PATCH `/api/system/settings` | API key from Radarr config |

### Indexers (Prowlarr)

| Indexer | Type | Configuration |
|---------|------|---------------|
| 1337x | Public | Default settings |
| 1337x (Tor) | Custom | Uses `tor-proxy:9050`, from `Definitions/Custom/` |

### Monitoring Profile

If `ENABLE_MONITORING_PROFILE=true` is set in `.env`, the bootstrap script will automatically start the monitoring exporters after saving API keys.

## Usage

### First-Time Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd torrent-services

# 2. Create and configure .env
cp .env.example .env
nano .env  # Add your VPN credentials and passwords

# 3. Start the stack
docker compose up -d

# 4. Wait for services to initialize (~30-60 seconds), then bootstrap
./scripts/bootstrap.sh
```

### Subsequent Starts

```bash
# Just start normally - no bootstrap needed
docker compose up -d
```

### Re-Running Bootstrap

The bootstrap script is **idempotent**. It checks for existing configurations and skips them, so it's safe to run multiple times:

```bash
./scripts/bootstrap.sh
```

Use cases for re-running:

- After an app regenerates its API key
- After manually deleting a connection
- To pick up new `.env` credential changes

## File Structure

```txt
torrent-services/
├── scripts/
│   └── bootstrap.sh          # The bootstrap script
├── config/
│   ├── prowlarr/
│   │   ├── config.xml        # Auto-generated (contains API key)
│   │   └── Definitions/
│   │       └── Custom/       # Custom indexer definitions (tracked)
│   ├── sonarr/
│   │   └── config.xml        # Auto-generated (not tracked)
│   ├── radarr/
│   │   └── config.xml        # Auto-generated (not tracked)
│   ├── bazarr/
│   │   └── config/
│   │       └── config.yaml   # Auto-generated (not tracked)
│   ├── qbittorrent/          # Auto-generated (not tracked)
│   └── gluetun/              # Auto-generated (not tracked)
├── docker-compose.yml
├── .env                      # Secrets (not tracked)
└── .env.example              # Template (tracked)
```

## Environment Variables

The `.env` file contains credentials and settings. See [`.env.example`](../.env.example) for the complete list with documentation.

Key variables used by bootstrap:

| Variable | Purpose |
|----------|---------|
| `QBIT_USER` / `QBIT_PASS` | qBittorrent Web UI credentials |
| `SONARR_USER` / `SONARR_PASS` | Sonarr authentication |
| `RADARR_USER` / `RADARR_PASS` | Radarr authentication |
| `PROWLARR_USER` / `PROWLARR_PASS` | Prowlarr authentication |
| `BAZARR_USER` / `BAZARR_PASS` | Bazarr authentication |
| `ENABLE_MONITORING_PROFILE` | Auto-start monitoring exporters if `true` |

## Verification

After running bootstrap, verify the configuration:

### Check Service Connections

| Check | Location |
|-------|----------|
| Prowlarr → Apps | Prowlarr UI → Settings → Apps (should show Sonarr, Radarr) |
| Sonarr → Download Client | Sonarr UI → Settings → Download Clients (should show qBittorrent) |
| Radarr → Download Client | Radarr UI → Settings → Download Clients (should show qBittorrent) |
| Bazarr → Apps | Bazarr UI → Settings (should show Sonarr, Radarr connected) |
| Prowlarr → Indexers | Prowlarr UI → Indexers (should show configured indexers) |

### Test End-to-End

1. Search for a show/movie in Sonarr/Radarr
2. Verify indexer results appear
3. Download something
4. Verify it appears in qBittorrent with correct category

## Troubleshooting

### Bootstrap Script Fails

1. **Check services are healthy:**

   ```bash
   docker compose ps
   ```

2. **Check logs for errors:**

   ```bash
   docker compose logs prowlarr --tail 50
   docker compose logs sonarr --tail 50
   ```

3. **Verify API keys were generated:**

   ```bash
   grep ApiKey config/sonarr/config.xml
   grep ApiKey config/radarr/config.xml
   ```

### Connection Already Exists

The script handles this gracefully by checking first. If you need to recreate:

1. Delete the existing connection in the app's UI
2. Re-run `./scripts/bootstrap.sh`

### API Key Mismatch

If an app regenerates its API key after bootstrap:

1. Delete the problematic connection in the UI
2. Re-run `./scripts/bootstrap.sh` to pick up the new key

### Services Not Healthy

If bootstrap times out waiting for services:

```bash
# Check which services are unhealthy
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check logs for the unhealthy service
docker compose logs <service-name> --tail 100
```

See [HEALTHCHECK.md](./HEALTHCHECK.md) for detailed healthcheck troubleshooting.
