# Media Automation Stack (Torrent Services)

Automated media download and management using Docker with Transmission, Gluetun, Prowlarr, Sonarr, Radarr, Bazarr, and ProtonVPN port forwarding.

## Features

| Tool | Purpose | Website |
|------|---------|---------|
| **Transmission** | Torrent client | [Transmission](https://transmissionbt.com) |
| **Gluetun** | VPN client with ProtonVPN & port forwarding | [Gluetun](https://github.com/qdm12/gluetun) |
| **Prowlarr** | Indexer management | [Prowlarr](https://prowlarr.com/) |
| **Sonarr** | TV show management | [Sonarr](https://sonarr.tv/) |
| **Radarr** | Movie management | [Radarr](https://radarr.video/) |
| **Bazarr** | Subtitle management | [Bazarr](https://www.bazarr.media) |

**VPN:** ProtonVPN with automatic port forwarding via Gluetun for optimal torrent performance and privacy.

## Quick Start

**Prerequisites**: Docker & Docker Compose ([Install](https://docs.docker.com/get-docker/)), ProtonVPN Plus subscription ([Sign up](https://protonvpn.com/))

**Deploy in 3 steps:**

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Set ProtonVPN credentials and Transmission password (see setup guide below)

# 2. Start services
docker compose up -d

# 3. Verify VPN and port forwarding
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json
docker exec gluetun cat /tmp/gluetun/forwarded_port
docker logs transmission-port-updater --tail 20
```

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

### Step 2: Configure Transmission Password

Set your Transmission credentials in the `.env` file before starting the stack.

1. **Edit `.env` and set your password:**

   ```bash
   nano .env
   # Set TRANSMISSION_PASS=your_password
   # Optionally set TRANSMISSION_USER=your_username (default: admin)
   ```

2. **Start the stack:**

   ```bash
   docker compose up -d
   ```

3. **Access Transmission:**
   - URL: `http://localhost:9091`
   - Username: `admin` (or your TRANSMISSION_USER)
   - Password: (your TRANSMISSION_PASS from .env)

### Step 3: Verify Automatic Port Forwarding

The `transmission-port-updater` container automatically watches for port changes and updates Transmission instantly when they occur.

```bash
# Check Gluetun's forwarded port
docker exec gluetun cat /tmp/gluetun/forwarded_port

# View port updater logs
docker logs transmission-port-updater --tail 20

# Verify Transmission is connectable (check status at http://localhost:9091)
```

You should see logs like:

```bash
✓ Found forwarded port: 51820
🔄 Updating Transmission port from 51413 to 51820
✓ Successfully updated Transmission port to: 51820
```

**That's it!** The port will automatically update whenever Gluetun reconnects or restarts.

### Step 4: Configure Prowlarr, Sonarr, and Radarr

#### Update Download Client URLs

Since Transmission runs inside Gluetun's network, access it via `gluetun:9091`

**Sonarr:**

1. Go to `http://localhost:8989`
2. Navigate to **Settings** → **Download Clients**
3. Edit or add Transmission:
   - Host: `gluetun`
   - Port: `9091`
   - Username/Password: (your Transmission credentials)
4. Click **Test** → **Save**

**Radarr:**

1. Go to `http://localhost:7878`
2. Navigate to **Settings** → **Download Clients**
3. Edit or add Transmission:
   - Host: `gluetun`
   - Port: `9091`
   - Username/Password: (your Transmission credentials)
4. Click **Test** → **Save**

**Prowlarr:**

1. Go to `http://localhost:9696`
2. If Transmission is configured as a download client:
   - Navigate to **Settings** → **Download Clients**
   - Edit or add Transmission:
     - Host: `gluetun`
     - Port: `9091`
     - Username/Password: (your Transmission credentials)
   - Click **Test** → **Save**

**Bazarr:** No configuration needed - doesn't interact with Transmission directly.

## How Automatic Port Forwarding Works

### The Process

1. **Gluetun starts** and connects to ProtonVPN P2P server
2. **ProtonVPN assigns** a forwarded port (changes on each connection)
3. **Gluetun saves** the port to `/tmp/gluetun/forwarded_port`
4. **transmission-port-updater watches** the file for changes using inotify
5. **Port automatically updates** in Transmission instantly when detected

### The transmission-port-updater Container

A lightweight Alpine Linux container runs alongside your stack:

- **Watches** Gluetun's forwarded port file for changes using inotify
- **Responds instantly** when the port changes
- **Authenticates** with Transmission using credentials from `.env`
- **Updates** Transmission's listening port automatically via RPC API
- **Logs** all port changes for monitoring

### Configuration

Edit `.env` to set your Transmission password:

```bash
# Required - your Transmission password
TRANSMISSION_PASS=your_password
```

### Monitoring

View the port updater logs:

```bash
# Live monitoring
docker logs -f transmission-port-updater

# Last 20 lines
docker logs transmission-port-updater --tail 20
```

**Access Services:**

| Service | URL | Local Domain | Network Access | Purpose |
|---------|-----|--------------|----------------|---------|
| Transmission | <http://localhost:9091> | <http://transmission.home.arpa:9091> | <http://192.168.1.254:9091> | Torrents |
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

- **Transmission:** `gluetun:9091` (Transmission shares Gluetun's network)
- **Other services:** Use container name (e.g., `prowlarr:9696`, `sonarr:8989`)

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
docker compose logs -f <service>                  # View logs (follow mode)

# VPN Testing
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json  # Check VPN connection
docker exec gluetun cat /tmp/gluetun/forwarded_port                  # Get forwarded port

# Port Forwarding
docker exec gluetun cat /tmp/gluetun/forwarded_port  # Check current forwarded port
docker logs transmission-port-updater --tail 20      # View port updater logs
docker logs -f transmission-port-updater             # Live monitoring of port updates

# Troubleshooting
docker compose ps                                 # Check container status
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
   docker logs transmission-port-updater --tail 20
   ```

   Look for successful updates or error messages

4. **Verify Connectivity:**
   - In Transmission, check the turtle/network icon
   - Should show a green indicator when port is open
   - May take 1-2 minutes after port change

### Transmission Shows Port Closed

1. **Check port updater is running:**

   ```bash
   docker ps | grep transmission-port-updater
   docker logs transmission-port-updater --tail 20
   ```

2. **Verify TRANSMISSION_PASS is set in .env:**

   ```bash
   grep TRANSMISSION_PASS .env
   ```

   If not set, add it and restart:

   ```bash
   echo "TRANSMISSION_PASS=your_password" >> .env
   docker compose restart transmission-port-updater
   ```

3. **Restart services:**

   ```bash
   docker compose restart transmission transmission-port-updater
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

### Sonarr/Radarr Can't Connect to Transmission

1. Verify hostname is `gluetun` not `transmission`
2. Verify port is `9091`
3. Test connection: `docker exec sonarr curl http://gluetun:9091`

## Security

- Never commit `.env` (contains ProtonVPN credentials - excluded via `.gitignore`)
- VPN kill-switch enabled: if VPN drops, Transmission loses internet access (no IP leak)
- Port forwarding managed automatically by ProtonVPN
- All torrent traffic routed through ProtonVPN tunnel
- Services accessible on local network (consider firewall rules if needed)
