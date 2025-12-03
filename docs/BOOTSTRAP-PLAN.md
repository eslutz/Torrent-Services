# Automated Service Bootstrap Plan

This document outlines the strategy and implementation plan for automatically configuring inter-service connections when deploying the torrent stack on a new host.

## Strategy

**Zero Config Files in Git**: The applications auto-generate their configurations on first boot, then use their APIs to:

1. Read the auto-generated API keys
2. Configure all inter-service connections
3. Set up indexers and download clients

This approach ensures that:

- No secrets are ever committed to git
- Each deployment has unique, secure API keys
- Configuration is reproducible and automated via script

## Architecture Overview

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
│     - Configures Prowlarr → Sonarr/Radarr apps                  │
│     - Configures Sonarr → qBittorrent download client           │
│     - Configures Radarr → qBittorrent download client           │
│     - Configures Bazarr → Sonarr/Radarr connections             │
│     - Adds Prowlarr indexers (public + custom definitions)      │
│     - Configures Bazarr subtitle providers                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Stack is fully operational                                  │
│     - All services connected                                    │
│     - Indexers synced to Sonarr/Radarr                          │
│     - Ready to use                                              │
└─────────────────────────────────────────────────────────────────┘
```

## What Gets Configured

### Authentication

| Service | Action | Credentials Source |
|---------|--------|-------------------|
| qBittorrent | Updates default/temp password | `QBIT_USER`/`PASS` in `.env` |
| Sonarr | Enables Forms Auth | `SONARR_USER`/`PASS` in `.env` |
| Radarr | Enables Forms Auth | `RADARR_USER`/`PASS` in `.env` |
| Prowlarr | Enables Forms Auth | `PROWLARR_USER`/`PASS` in `.env` |
| Bazarr | Enables Forms Auth | `BAZARR_USER`/`PASS` in `.env` |

### Service Connections

| Connection | Method | Data Source |
|------------|--------|-------------|
| Prowlarr → Sonarr | POST `/api/v1/applications` | API key read from Sonarr config |
| Prowlarr → Radarr | POST `/api/v1/applications` | API key read from Radarr config |
| Sonarr → qBittorrent | POST `/api/v3/downloadclient` | Credentials from `.env` |
| Radarr → qBittorrent | POST `/api/v3/downloadclient` | Credentials from `.env` |
| Bazarr → Sonarr | PATCH `/api/system/settings` | API key read from Sonarr config |
| Bazarr → Radarr | PATCH `/api/system/settings` | API key read from Radarr config |

### Indexers (Prowlarr)

| Indexer | Type | Configuration |
|---------|------|---------------|
| 1337x | Public | Default settings |
| 1337x (Tor) | Custom | Uses `tor-proxy:9050`, from `Definitions/Custom/` |
| IPTorrents | Private | Cookie from `.env` (optional) |

### Subtitle Providers (Bazarr)

| Provider | Configuration |
|----------|---------------|
| Addic7ed | Username/password/cookies from `.env` |
| OpenSubtitles.com | Username/password from `.env` |

## Environment Variables

The `.env` file contains credentials that cannot be auto-generated. Please refer to the [`.env.example`](../.env.example) file for the complete list of supported variables and configuration options.

## Files Structure

```txt
torrent-services/
├── scripts/
│   └── bootstrap.sh          # Unified bootstrap script
├── config/
│   ├── prowlarr/
│   │   └── Definitions/
│   │       └── Custom/       # Custom indexer definitions (tracked)
│   │           └── 1337x-tor.yml
│   ├── sonarr/               # Auto-generated (not tracked)
│   ├── radarr/               # Auto-generated (not tracked)
│   ├── bazarr/               # Auto-generated (not tracked)
│   ├── qbittorrent/          # Auto-generated (not tracked)
│   └── gluetun/              # Auto-generated (not tracked)
├── docker-compose.yml
├── .env                      # Secrets (not tracked)
└── .env.example              # Template (tracked)
```

## Usage

> **Note:** The bootstrap script is idempotent. It checks for existing configurations and skips them, so it is safe to run multiple times if needed.

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

# 4. Wait for services to initialize (about 30-60 seconds)
# Then run the bootstrap script
./scripts/bootstrap.sh
```

### Subsequent Starts

```bash
# Just start normally - no bootstrap needed
docker compose up -d
```

## Success Criteria

After running `./scripts/bootstrap.sh`:

- [ ] All services have authentication enabled with credentials from `.env`
- [ ] Prowlarr shows Sonarr and Radarr in Settings → Apps
- [ ] Sonarr shows qBittorrent in Settings → Download Clients
- [ ] Radarr shows qBittorrent in Settings → Download Clients
- [ ] Bazarr shows Sonarr and Radarr in Settings
- [ ] Prowlarr has indexers configured
- [ ] Indexers are synced to Sonarr and Radarr
- [ ] Adding a show/movie triggers search on indexers
- [ ] Downloads are sent to qBittorrent with correct category

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
   cat config/sonarr/config.xml | grep ApiKey
   cat config/radarr/config.xml | grep ApiKey
   ```

### Connection Already Exists Error

The script handles this gracefully by checking first. If you need to recreate:

1. Delete the existing connection in the UI
2. Re-run `./scripts/bootstrap.sh`

### API Key Mismatch

If apps regenerate keys after bootstrap:

1. Delete the problematic connection in the UI
2. Re-run `./scripts/bootstrap.sh` to pick up new keys
