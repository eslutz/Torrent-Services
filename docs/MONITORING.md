# Monitoring Stack

This document describes the Prometheus metrics exporters used for monitoring the torrent services stack.

## Overview

The stack includes two Prometheus exporters under the `monitoring` profile:

| Exporter | Metrics For | Port | Image |
|----------|-------------|------|-------|
| **qbittorrent-exporter** | qBittorrent | 8090 | `ghcr.io/martabal/qbittorrent-exporter` |
| **Scraparr** | Sonarr, Radarr, Prowlarr, Bazarr | 7100 | `ghcr.io/thecfu/scraparr` |

These exporters expose metrics at `/metrics` endpoints in Prometheus format. They **do not store data**—each scrape returns a snapshot of current state.

## Architecture

```txt
┌──────────────┐     scrape /metrics     ┌────────────┐     query      ┌────────────┐
│  Exporters   │ ◄────────────────────── │ Prometheus │ ◄───────────── │  Grafana   │
│ (this stack) │                         │ (external) │                │ (external) │
└──────────────┘                         └────────────┘                └────────────┘
       │                                       │                             │
 export current                            store time                    visualize
 metrics only                              series data                   from Prometheus
```

**Understanding the components**:

1. **Exporters** (this stack): Expose current metrics at `/metrics`. No storage.
2. **Prometheus** (external): Scrapes endpoints periodically and stores time-series data.
3. **Grafana** (external): Queries Prometheus to visualize trends and history.

> **Note**: Prometheus and Grafana typically run on a dedicated monitoring host (e.g., in your `network-services` stack on Pi 5).

## Quick Start

### Prerequisites

1. Run `./scripts/bootstrap.sh` first—it extracts API keys and saves them to `.env`
2. API keys in `.env`: `SONARR_API_KEY`, `RADARR_API_KEY`, `PROWLARR_API_KEY`, `BAZARR_API_KEY`

### Start Monitoring

**Option A. Auto-start with bootstrap:**

Set `ENABLE_MONITORING_PROFILE=true` in `.env` before running bootstrap:

```bash
# Edit .env
ENABLE_MONITORING_PROFILE=true

# Bootstrap will start monitoring containers automatically
./scripts/bootstrap.sh
```

**Option B. Manual start:**

```bash
# Start monitoring containers
docker compose --profile monitoring up -d qbittorrent-exporter scraparr
```

### Stop Monitoring

```bash
docker compose --profile monitoring down
```

### Verify Metrics

```bash
# qBittorrent metrics
curl http://127.0.0.1:8090/metrics

# *arr metrics (Sonarr, Radarr, Prowlarr, Bazarr)
curl http://127.0.0.1:7100/metrics
```

## Exporter Details

### qBittorrent Exporter

**Image**: `ghcr.io/martabal/qbittorrent-exporter:latest`

**Why this exporter**:

- Written in Go (low resource usage, ~10MB image)
- Actively maintained (regular releases)
- Supports trackers, tags, and categories
- Includes Grafana dashboard

**Configuration** (via environment variables):

| Variable | Default | Purpose |
|----------|---------|---------|
| `QBITTORRENT_BASE_URL` | `http://gluetun:8080` | qBittorrent API URL |
| `QBITTORRENT_USERNAME` | `admin` | Web UI username |
| `QBITTORRENT_PASSWORD` | (from `.env`) | Web UI password |
| `EXPORTER_PORT` | `8090` | Metrics port |
| `ENABLE_TRACKER` | `true` | Enable tracker metrics |

**Metrics exposed** (examples):

- `qbittorrent_torrents_count` - Total number of torrents
- `qbittorrent_global_download_speed_bytes` - Current download speed
- `qbittorrent_global_upload_speed_bytes` - Current upload speed
- `qbittorrent_torrent_progress` - Per-torrent download progress

### Scraparr

**Image**: `ghcr.io/thecfu/scraparr:latest`

**Why Scraparr**:

- Single container for all *arr apps (vs. 4 separate Exportarr containers)
- Actively maintained
- Environment variable configuration
- Includes Grafana dashboards

**Configuration** (via environment variables):

| Variable | Purpose |
|----------|---------|
| `GENERAL_PORT` | Metrics port (7100) |
| `SONARR_URL` / `SONARR_API_KEY` | Sonarr connection |
| `RADARR_URL` / `RADARR_API_KEY` | Radarr connection |
| `PROWLARR_URL` / `PROWLARR_API_KEY` | Prowlarr connection |
| `BAZARR_URL` / `BAZARR_API_KEY` | Bazarr connection |
| `*_INTERVAL` | Scrape interval per app (30s) |

**Metrics exposed** (examples):

- `sonarr_series_total` - Total TV series
- `radarr_movies_total` - Total movies
- `prowlarr_indexers_total` - Configured indexers
- `bazarr_episodes_total` - Episodes with subtitles

## Prometheus Configuration

Add these scrape targets to your Prometheus configuration:

```yaml
scrape_configs:
  # qBittorrent metrics
  - job_name: 'qbittorrent'
    static_configs:
      - targets: ['192.168.50.100:8090']  # Gaming PC IP

  # *arr metrics (Sonarr, Radarr, Prowlarr, Bazarr)
  - job_name: 'scraparr'
    static_configs:
      - targets: ['192.168.50.100:7100']  # Gaming PC IP
```

> **Note**: Ports are bound to `127.0.0.1` by default. If Prometheus runs on a different host, update the port bindings in `docker-compose.yml` to expose on the LAN IP.

## Grafana Dashboards

Both exporters include Grafana dashboards:

| Exporter | Dashboard Source |
|----------|------------------|
| qbittorrent-exporter | [GitHub repo](https://github.com/martabal/qbittorrent-exporter) |
| Scraparr | [GitHub repo](https://github.com/thecfu/scraparr) |

Import these JSON files into Grafana for pre-built visualizations.

## Resource Limits

Configurable via `.env`:

```bash
# qBittorrent exporter
QBITTORRENT_EXPORTER_MEM_LIMIT="128m"
QBITTORRENT_EXPORTER_CPUS="0.25"

# Scraparr
SCRAPARR_MEM_LIMIT="256m"
SCRAPARR_CPUS="0.5"
```

## Troubleshooting

### Scraparr Returns 401/403

API keys are missing or incorrect:

```bash
# Check if API keys are in .env
grep "_API_KEY" .env

# If empty, re-run bootstrap
./scripts/bootstrap.sh
```

### Exporter Container Won't Start

Check dependencies are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Exporters depend on their target services being healthy first.

### Metrics Show Zeros

1. Verify the target service is running and accessible
2. Check exporter logs:

   ```bash
   docker logs qbittorrent-exporter --tail 50
   docker logs scraparr --tail 50
   ```

### Can't Access Metrics from Remote Host

Ports are bound to `127.0.0.1` (localhost only). To expose on LAN:

1. Edit `docker-compose.yml`:

   ```yaml
   ports:
     - "8090:8090"  # Remove 127.0.0.1 prefix
   ```

2. Restart the exporter:

   ```bash
   docker compose --profile monitoring up -d
   ```

## References

- [martabal/qbittorrent-exporter](https://github.com/martabal/qbittorrent-exporter)
- [Scraparr](https://github.com/thecfu/scraparr)
- [Prometheus Documentation](https://prometheus.io/docs/)
