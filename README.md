# Media Automation Stack (Torrent Services)

Automated media download and management using Docker with Sonarr, Radarr, qBittorrent, and VPN protection.

## Features

| Tool | Purpose | Website |
|------|---------|---------|
| **qBittorrent** | Torrent client | [qBittorrent](https://www.qbittorrent.org) |
| **Gluetun** | VPN client with kill-switch (Mullvad) | [Gluetun](https://github.com/qdm12/gluetun) |
| **Sonarr** | TV show management | [Sonarr](https://sonarr.tv/) |
| **Radarr** | Movie management | [Radarr](https://radarr.video/) |
| **Prowlarr** | Indexer management | [Prowlarr](https://prowlarr.com/) |
| **Bazarr** | Subtitle management | [Bazarr](https://www.bazarr.media) |

**VPN:** Mullvad WireGuard with automatic kill-switch. See [VPN Guide](../docs/torrent-stack/vpn-guide.md) for setup.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), Mullvad VPN subscription ([Sign up](https://mullvad.net/))

**Deploy in 3 steps:**

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Set Mullvad credentials (see VPN Guide)

# 2. Start services
docker-compose up -d

# 3. Verify VPN
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected
```

**Mullvad Configuration:** Set Mullvad WireGuard credentials in `.env`. See [VPN Guide](../docs/torrent-stack/vpn-guide.md) for detailed setup.

**Access Services:**

| Service | URL | Local Domain | Network Access | Purpose |
|---------|-----|--------------|----------------|---------|
| qBittorrent | http://localhost:8080 | http://qbittorrent.home.arpa:8080 | http://192.168.1.254:8080 | Torrents |
| Sonarr | http://localhost:8989 | http://sonarr.home.arpa:8989 | http://192.168.1.254:8989 | TV shows |
| Radarr | http://localhost:7878 | http://radarr.home.arpa:7878 | http://192.168.1.254:7878 | Movies |
| Prowlarr | http://localhost:9696 | http://prowlarr.home.arpa:9696 | http://192.168.1.254:9696 | Indexers |
| Bazarr | http://localhost:6767 | http://bazarr.home.arpa:6767 | http://192.168.1.254:6767 | Subtitles |

**Addressing Guide:**
- **localhost** - Access from the same machine running Docker
- **home.arpa domains** - Network access after adding DNS records to Pi-hole (see [Network Integration](../docs/torrent-stack/network-integration.md))
- **Network Access (192.168.1.254:port)** - Direct IP access from any device on your home network
- **service:port** (e.g., `prowlarr:9696`) - Inter-container communication only (used in service configuration)

**How to Access from Other Computers:**

All services are accessible over your home network using the Network Access URLs above.

1. **Find the server IP:** Run `ifconfig | grep "inet " | grep -v 127.0.0.1` on the server to get its IP (currently: `192.168.1.254`)
2. **Access via browser:** Use `http://<SERVER_IP>:<PORT>` from any device on your network
3. **Bookmark for convenience:** Save the URLs in your browser

**For Inter-container Communication:**
When configuring services to talk to each other (e.g., Sonarr connecting to qBittorrent), use:
- qBittorrent: `gluetun:8080` (because qBittorrent shares Gluetun's network)
- Other services: Use container name (e.g., `prowlarr:9696`, `sonarr:8989`)

**qBittorrent password:** `docker logs qbittorrent 2>&1 | grep "temporary password"`

## Documentation

- **[Initial Setup](../docs/torrent-stack/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-stack/vpn-guide.md)** - Mullvad VPN setup and troubleshooting
- **[Network Integration](../docs/torrent-stack/network-integration.md)** - Home network architecture integration
- **[Maintenance](../docs/torrent-stack/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-stack/architecture-overview.md)** - Technical overview

## Common Commands

```bash
docker-compose up -d                              # Start services
docker-compose down                               # Stop all
docker-compose logs -f <service>                  # View logs
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected  # Check VPN
./speedtest-vpn.sh                                # Test VPN download speed
```

## Security

- Never commit `.env` (contains Mullvad credentials - excluded via `.gitignore`)
- VPN always enabled for torrenting
- kill-switch prevents IP exposure if VPN drops
- Services accessible on local network (consider firewall rules if needed for additional security)
