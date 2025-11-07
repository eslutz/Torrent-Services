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

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone <your-repo-url> && cd torrent-stack
cp .env.example .env

# 2. Choose and configure your VPN provider
# Edit .env with your VPN credentials:
#   - For Mullvad: WIREGUARD_PRIVATE_KEY and WIREGUARD_ADDRESSES
#   - For NordVPN/ProtonVPN/Surfshark: OPENVPN_USER and OPENVPN_PASSWORD
#   - For other providers: Check ../docs/torrent-stack/vpn-guide.md for generic setup
#   - Set VPN_SERVICE_PROVIDER to your provider name (exact match required)
# See ../docs/torrent-stack/vpn-guide.md for provider-specific instructions

# 3. Run setup and start
chmod +x setup.sh && ./setup.sh
docker-compose --profile vpn up -d
```

**Access services:**

| Service | Port |
|---|---|
| Sonarr | 8989 |
| Radarr | 7878 |
| qBittorrent | 8080 |
| Prowlarr | 9696 |
| Bazarr | 6767 |

**Get qBittorrent password:**

```bash
docker logs qbittorrent 2>&1 | grep "temporary password"
```

**Verify VPN connection (works for all providers):**

```bash
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected
```

## 📚 Documentation

- **[Initial Setup](../docs/torrent-stack/initial-setup.md)** - Complete configuration walkthrough
- **[VPN Guide](../docs/torrent-stack/vpn-guide.md)** - VPN setup and mode switching
- **[Maintenance](../docs/torrent-stack/maintenance.md)** - Updates, backups, troubleshooting
- **[Architecture](../docs/torrent-stack/architecture-overview.md)** - Technical overview

## 🔧 Common Commands

```bash
docker-compose --profile vpn up -d           # Start with VPN
docker-compose down                          # Stop all
docker-compose restart <service>             # Restart one
docker-compose logs -f <service>             # View logs
docker exec gluetun wget -qO- https://am.i.mullvad.net/connected  # Check VPN (all providers)
```

## ⚠️ Security

🔒 Never commit `.env` (contains VPN credentials). Always use VPN mode for torrenting. Kill switch ensures qBittorrent loses internet if VPN drops. Works with all supported VPN providers.
