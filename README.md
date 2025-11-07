# Media Automation Server

Automated media download and management stack using Docker with Sonarr, Radarr, qBittorrent, and VPN protection.

## 🎯 Features

| Tool | Purpose | Website |
| --- | --- | --- |
| 🌊 **qBittorrent** | Torrent client | [qBittorrent](https://www.qbittorrent.org) |
| 🔒 **Gluetun** | VPN client with kill switch | [Gluetun](https://github.com/qdm12/gluetun) |
| �️ **Multi-VPN Support** | 30+ VPN providers | [Providers](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers) |
| 🎬 **Radarr** | Movies | [Radarr](https://radarr.video/) |
| 📺 **Sonarr** | TV Shows | [Sonarr](https://sonarr.tv/) |
| 🔍 **Prowlarr** | Indexers | [Prowlarr](https://prowlarr.com/) |
| 💬 **Bazarr** | Subtitles | [Bazarr](https://www.bazarr.media) |

## Supported VPN Providers

Choose from **20+ VPN providers** including:

- **Mullvad** (default) - Privacy-focused, €5/month
- **ProtonVPN** - Free tier available, Swiss privacy
- **NordVPN** - Large network, good speeds
- **Surfshark** - Unlimited devices, good value
- **Private Internet Access** - Port forwarding support
- **ExpressVPN**, **IPVanish**, **CyberGhost**, **Windscribe**, **IVPN**, **AirVPN**, and more

[Full provider list](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers)

**Any provider supported by Gluetun works with this stack!** See the [VPN Guide](../docs/torrent-stack/vpn-guide.md) for setup instructions.

## Prerequisites

- Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/))
- VPN subscription from a [supported provider](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers)

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), VPN subscription from a [supported provider](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers)

**Setup and deployment:**

```bash
# 1. Navigate to torrent-stack directory
cd torrent-stack

# 2. Configure environment
cp .env.example .env
nano .env  # Configure VPN credentials (see VPN Guide)

# 3. Run setup script and start services
chmod +x setup.sh && ./setup.sh
docker-compose --profile vpn up -d
```

**VPN configuration** (edit `.env`):

- **Mullvad**: Set `WIREGUARD_PRIVATE_KEY` and `WIREGUARD_ADDRESSES`
- **NordVPN/ProtonVPN/Surfshark**: Set `OPENVPN_USER` and `OPENVPN_PASSWORD`
- **Other providers**: See [VPN Guide](../docs/torrent-stack/vpn-guide.md) for provider-specific setup
- Set `VPN_SERVICE_PROVIDER` to your provider name (exact match required)

**Access services:**

| Service | URL | Purpose |
|---------|-----|---------|
| Sonarr | http://localhost:8989 | TV show management |
| Radarr | http://localhost:7878 | Movie management |
| qBittorrent | http://localhost:8080 | Torrent client |
| Prowlarr | http://localhost:9696 | Indexer management |
| Bazarr | http://localhost:6767 | Subtitle management |

**Initial qBittorrent password:**

```bash
docker logs qbittorrent 2>&1 | grep "temporary password"
```

**Verify VPN connection:**

```bash
# Works for all VPN providers
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected

# Check your VPN IP address
docker exec gluetun wget -qO- https://icanhazip.com
```

## Documentation

- **[Network Integration](../docs/torrent-stack/network-integration.md)** - Integration with home network architecture
- **[Initial Setup](../docs/torrent-stack/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-stack/vpn-guide.md)** - VPN setup and mode switching
- **[Maintenance](../docs/torrent-stack/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-stack/architecture-overview.md)** - Technical overview

## Common Commands

```bash
docker-compose --profile vpn up -d           # Start with VPN
docker-compose down                          # Stop all
docker-compose restart <service>             # Restart one
docker-compose logs -f <service>             # View logs
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected  # Check VPN (all providers)
```

## Security

**Important security notes:**

- Never commit `.env` file (contains VPN credentials) - already excluded via `.gitignore`
- Always use VPN mode for torrenting to protect your privacy
- Kill switch ensures qBittorrent loses internet access if VPN connection drops
- Works with all 30+ supported VPN providers for flexible privacy options
- qBittorrent Web UI bound to localhost only (127.0.0.1:8080) for additional security
