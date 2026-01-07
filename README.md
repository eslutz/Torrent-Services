# Torrent-Services

Media automation stack with qBittorrent, Gluetun (VPN), Prowlarr, Sonarr, Radarr, Bazarr, Unpackerr, Tdarr, Forwardarr, and optional monitoring/exporters.

[![CI Pipeline](https://github.com/eslutz/Torrent-Services/actions/workflows/ci.yml/badge.svg)](https://github.com/eslutz/Torrent-Services/actions/workflows/ci.yml) [![Security Analysis](https://github.com/eslutz/Torrent-Services/actions/workflows/security.yml/badge.svg)](https://github.com/eslutz/Torrent-Services/actions/workflows/security.yml)

## What's Included

| Component | Local URL | Details |
| --- | --- | --- |
| [qBittorrent](https://www.qbittorrent.org) | <http://localhost:8080> | Torrent client behind VPN; use `gluetun:8080` from other containers |
| [Gluetun](https://github.com/qdm12/gluetun) | n/a | VPN client (WireGuard/OpenVPN) with optional port forwarding; shared network namespace for qBittorrent |
| [Prowlarr](https://github.com/Prowlarr/Prowlarr) | <http://localhost:9696> | Indexer manager feeding Sonarr/Radarr; configure indexers first |
| [Sonarr](https://github.com/Sonarr/Sonarr) | <http://localhost:8989> | TV show automation; API key set in app UI and `.env` |
| [Radarr](https://github.com/Radarr/Radarr) | <http://localhost:7878> | Movie automation; API key set in app UI and `.env` |
| [Bazarr](https://github.com/morpheus65535/bazarr) | <http://localhost:6767> | Subtitles; configure providers via UI |
| [Unpackerr](https://github.com/Unpackerr/unpackerr) | <http://localhost:5656> | Extracts completed downloads for *arr apps; metrics only |
| [Tdarr](https://github.com/HaveAGitGat/Tdarr) | <http://localhost:8265> | Optional transcoding with helper scripts for extra nodes; use scripts to add nodes |
| [Forwardarr](https://github.com/eslutz/Forwardarr) | <http://127.0.0.1:9090/metrics> | Syncs VPN forwarded port into qBittorrent; port sync + metrics |
| [Torarr](https://github.com/eslutz/Torarr) (optional) | <http://127.0.0.1:8085/metrics> | SOCKS5 proxy for Tor-only indexers; Tor bootstrap/metrics |
| [Scraparr](https://github.com/thecfu/scraparr) / [qbittorrent-exporter](https://github.com/martabal/qbittorrent-exporter) (optional) | <http://127.0.0.1:7100/metrics> / <http://127.0.0.1:8090/metrics> | Prometheus metrics for qBittorrent, Forwardarr, Torarr, *arr apps; exporters only |
| [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) (optional) | <http://localhost:5055> | Requests UI; connect to Sonarr/Radarr |

### Core Patterns

- Backup/restore first: configure via web UIs, then capture state with `scripts/utilities/backup_config.sh`; restore with `scripts/utilities/restore_config.sh`.
- VPN network sharing: qBittorrent runs with `network_mode: service:gluetun`; in other services, reach it at `gluetun:8080`.
- Health-gated startup: each service waits for real API health checks (<5s) before others start; autoheal restarts unhealthy containers.
- Resource limits: controlled by env vars in `.env` (mem/cpu defaults per service); no YAML edits required.

## Quick Start (fresh install)

For step-by-step details, see [scripts/setup/README.md](scripts/setup/README.md).

```bash
cp .env.example .env
# Edit .env: VPN credentials, service passwords, resource limits
docker compose up -d
# Configure Prowlarr, Sonarr, Radarr, Bazarr, qBittorrent via their UIs
./scripts/utilities/backup_config.sh
```

## Quick Restore (from backup)

```bash
./scripts/utilities/restore_config.sh ./backups/<timestamp>
# Follow on-screen UI restore steps for *arr apps
docker compose ps
```

## VPN Setup

- Use any VPN provider supported by Gluetun (WireGuard or OpenVPN). Port forwarding improves seeding; choose a provider/location that offers it.
- Populate `.env` with the provider config from `.env.example` (e.g., `WIREGUARD_PRIVATE_KEY`, `WIREGUARD_ADDRESSES`, or OpenVPN creds). Leave empty values blank until you have them.
- Start the stack, then verify:

```bash
docker compose logs gluetun --tail 50         # tunnel up and provider details
docker exec gluetun cat /tmp/gluetun/forwarded_port  # forwarded port (if supported)
docker logs forwardarr --tail 20              # qBittorrent port sync
```

If your provider does not support forwarding, Forwardarr will log that no port was found; the stack still works, but seeding may be slower.

## Health, Autoheal, Monitoring

- Health scripts live in `scripts/healthchecks/` and gate startup; check with `docker compose ps` for `healthy` statuses.
- Autoheal monitors container health and restarts stuck services.
- Monitoring profile (optional): set `ENABLE_MONITORING_PROFILE=true` in `.env`, then run `docker compose --profile monitoring up -d` for exporters. Prometheus/Grafana are not bundled.

### Exporter endpoints (localhost only)

| Service | Endpoint |
| --- | --- |
| qBittorrent exporter | <http://127.0.0.1:8090/metrics> |
| Forwardarr | <http://127.0.0.1:9090/metrics> |
| Torarr | <http://127.0.0.1:8085/metrics> |
| Scraparr (*arr aggregate) | <http://127.0.0.1:7100/metrics> |

## Common commands

```bash
docker compose up -d                         # Start stack
docker compose down                          # Stop stack
docker compose restart <service>             # Restart one service
docker compose logs -f <service>             # Tail logs
docker compose --profile monitoring up -d    # Start exporters
./scripts/utilities/backup_config.sh         # Snapshot configs
./scripts/utilities/restore_config.sh <dir>  # Restore configs
```

## Tdarr node helpers

- Add a node: `./scripts/utilities/start_tdarr_node.sh`
- Manage nodes: `./scripts/utilities/manage_tdarr_nodes.sh list|stop|stop-all`
- Per-node overrides: flags on the helper scripts (CPU/GPU workers, limits) or env vars in `.env`.

## Troubleshooting quick checks

- VPN/port forwarding: `docker exec gluetun cat /tmp/gluetun/forwarded_port`; if empty, confirm provider supports forwarding and restart Gluetun.
- qBittorrent unconnectable: verify Forwardarr logs show a port update; ensure `QBITTORRENT_PASSWORD` is set in `.env`; restart `qbittorrent` and `forwardarr`.
- *arr cannot reach qBittorrent: host should be `gluetun` and port `8080`; test from a container: `docker exec sonarr curl -sf http://gluetun:8080`.
- Slow health startup: check scripts in `scripts/healthchecks/` and confirm upstream services are reachable; health checks time out after ~5s.

## Security

- Never commit `.env` (contains VPN credentials and service secrets; excluded via `.gitignore`)
- VPN kill-switch enforced: if the tunnel drops, qBittorrent loses internet access
- Port forwarding (when supported by your VPN) is synced automatically into qBittorrent via Forwardarr
- All torrent traffic is forced through the VPN interface

## Contributing

- Open issues or pull requests on GitHub with a clear description and reproduction steps if applicable.
- Follow existing patterns and environment-based configuration; do not hardcode credentials or resource limits.
- Run `venv/bin/pre-commit run --all-files` before submitting.
