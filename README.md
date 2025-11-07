# Media Automation Stack (Torrent Services)

Automated media download and management using Docker with Sonarr, Radarr, qBittorrent, and VPN protection.

## Features

| Tool | Purpose | Website |
|------|---------|---------|
| **qBittorrent** | Torrent client | [qBittorrent](https://www.qbittorrent.org) |
| **Gluetun** | VPN client with kill switch | [Gluetun](https://github.com/qdm12/gluetun) |
| **Sonarr** | TV show management | [Sonarr](https://sonarr.tv/) |
| **Radarr** | Movie management | [Radarr](https://radarr.video/) |
| **Prowlarr** | Indexer management | [Prowlarr](https://prowlarr.com/) |
| **Bazarr** | Subtitle management | [Bazarr](https://www.bazarr.media) |

**VPN Support:** 30+ providers including Mullvad, ProtonVPN, NordVPN, Surfshark, PIA, and more. See [VPN Guide](../docs/torrent-stack/vpn-guide.md) for complete list.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), VPN subscription

**Deploy in 3 steps:**

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Set VPN credentials (see VPN Guide)

# 2. Start services
docker-compose --profile vpn up -d

# 3. Verify VPN
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected
```

**VPN Configuration:** Set `VPN_SERVICE_PROVIDER`, `VPN_TYPE`, and provider credentials in `.env`. See [VPN Guide](../docs/torrent-stack/vpn-guide.md) for detailed setup.

**Access Services:**

| Service | URL | Local Domain | Purpose |
|---------|-----|--------------|---------|
| Sonarr | http://localhost:8989 | http://sonarr.home.arpa:8989 | TV shows |
| Radarr | http://localhost:7878 | http://radarr.home.arpa:7878 | Movies |
| qBittorrent | http://localhost:8080 | http://qbittorrent.home.arpa:8080 | Torrents |
| Prowlarr | http://localhost:9696 | http://prowlarr.home.arpa:9696 | Indexers |
| Bazarr | http://localhost:6767 | http://bazarr.home.arpa:6767 | Subtitles |

**qBittorrent password:** `docker logs qbittorrent 2>&1 | grep "temporary password"`

## Documentation

- **[Initial Setup](../docs/torrent-stack/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-stack/vpn-guide.md)** - VPN provider setup (30+ providers)
- **[Network Integration](../docs/torrent-stack/network-integration.md)** - Home network architecture integration
- **[Maintenance](../docs/torrent-stack/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-stack/architecture-overview.md)** - Technical overview

## Common Commands

```bash
docker-compose --profile vpn up -d           # Start with VPN
docker-compose down                          # Stop all
docker-compose logs -f <service>             # View logs
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected  # Check VPN
```

## Security

- Never commit `.env` (contains VPN credentials - excluded via `.gitignore`)
- Always use VPN mode for torrenting
- Kill switch prevents IP exposure if VPN drops
- qBittorrent bound to localhost by default (change in docker-compose.yml if network access needed)
