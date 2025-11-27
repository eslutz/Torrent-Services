# Media Automation Stack (Torrent Services)

Automated media download and management using Docker with Sonarr, Radarr, qBittorrent, and host-level VPN protection.

## Features

| Tool | Purpose | Website |
|------|---------|---------|
| **qBittorrent** | Torrent client | [qBittorrent](https://www.qbittorrent.org) |
| **Sonarr** | TV show management | [Sonarr](https://sonarr.tv/) |
| **Radarr** | Movie management | [Radarr](https://radarr.video/) |
| **Prowlarr** | Indexer management | [Prowlarr](https://prowlarr.com/) |
| **Bazarr** | Subtitle management | [Bazarr](https://www.bazarr.media) |

**VPN:** Mullvad VPN installed on host system for cleaner network routing and better private tracker connectivity.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), Mullvad VPN ([Install](https://mullvad.net/download))

**Deploy in 3 steps:**

```bash
# 1. Install and configure Mullvad VPN on your host system
# Download from: https://mullvad.net/download
# Or via Homebrew: brew install --cask mullvad-vpn
# Enable kill-switch and local network sharing in Mullvad settings

# 2. Configure environment
cp .env.example .env
nano .env  # Set PUID, PGID, TZ, and DATA_DIR

# 3. Start services
docker compose up -d
```

**Mullvad Configuration:**

- Install Mullvad app on your Mac/host system
- Enable "Always require VPN" (kill-switch)
- Enable "Local network sharing" (allows Docker containers to communicate)
- All Docker traffic automatically routes through Mullvad via host networking

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
- **home.arpa domains** - Network access after adding DNS records to Pi-hole (see [Network Integration](../docs/torrent-stack/network-integration.md))
- **Network Access (192.168.1.254:port)** - Direct IP access from any device on your home network
- **service:port** (e.g., `qbittorrent:8080`) - Inter-container communication only (used in service configuration)

**How to Access from Other Computers:**

All services are accessible over your home network using the Network Access URLs above.

1. **Find the server IP:** Run `ifconfig | grep "inet " | grep -v 127.0.0.1` on the server to get its IP (currently: `192.168.1.254`)
2. **Access via browser:** Use `http://<SERVER_IP>:<PORT>` from any device on your network
3. **Bookmark for convenience:** Save the URLs in your browser

**For Inter-container Communication:**
When configuring services to talk to each other (e.g., Sonarr connecting to qBittorrent), use container names:

- qBittorrent: `qbittorrent:8080`
- Other services: `prowlarr:9696`, `sonarr:8989`, etc.

**qBittorrent password:** `docker logs qbittorrent 2>&1 | grep "temporary password"`

## Documentation

- **[Initial Setup](../docs/torrent-stack/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-stack/vpn-guide.md)** - Mullvad VPN setup and troubleshooting
- **[Network Integration](../docs/torrent-stack/network-integration.md)** - Home network architecture integration
- **[Maintenance](../docs/torrent-stack/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-stack/architecture-overview.md)** - Technical overview

## Common Commands

```bash
# Service Management
docker compose up -d                              # Start services
docker compose down                               # Stop all
docker compose restart <service>                  # Restart specific service
docker compose logs -f <service>                  # View logs (follow mode)

# VPN Testing (from inside qBittorrent container)
docker exec qbittorrent curl https://am.i.mullvad.net/json  # Verify VPN connection
docker exec qbittorrent curl https://ipinfo.io/ip           # Check IP address

# Troubleshooting
docker compose ps                                 # Check container status
docker logs qbittorrent 2>&1 | grep "temporary password"  # Get qBittorrent temp password
```

## Security

- Never commit `.env` (excluded via `.gitignore`)
- Mullvad VPN runs at host level with kill-switch enabled
- Kill-switch prevents IP exposure if VPN drops
- Services accessible on local network (consider firewall rules if needed for additional security)
- All Docker traffic automatically routed through host's VPN connection
