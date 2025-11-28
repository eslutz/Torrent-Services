# ProtonVPN Port Forwarding Setup Guide

This guide explains how automatic port forwarding works with ProtonVPN and Gluetun, and how to configure qBittorrent to use it.

## Table of Contents

- [Why Port Forwarding Matters](#why-port-forwarding-matters)
- [Requirements](#requirements)
- [How It Works](#how-it-works)
- [Initial Setup](#initial-setup)
- [Port Forwarding Configuration](#port-forwarding-configuration)
- [Automated Port Updates](#automated-port-updates)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Why Port Forwarding Matters

### Without Port Forwarding

- You can only **initiate** connections to peers (outgoing)
- Other peers **cannot connect to you** (incoming blocked)
- Slower downloads, especially on torrents with few seeds
- Poor performance on private trackers
- May appear as "unconnectable" to trackers

### With Port Forwarding

- Peers can **connect directly to you** (incoming allowed)
- Faster downloads from more peers
- Better ratio on private trackers
- Improved swarm participation
- Shows as "connectable" to trackers

## Requirements

### ProtonVPN Subscription

- **Plus plan or higher** required
- Free plan does **NOT** support port forwarding
- Sign up at: <https://protonvpn.com/>

### P2P Server Selection

Port forwarding only works on ProtonVPN's P2P servers.

**Supported Countries:**

- 🇳🇱 Netherlands
- 🇮🇸 Iceland
- 🇸🇪 Sweden
- 🇨🇭 Switzerland
- 🇸🇬 Singapore

Check ProtonVPN website for updated list of P2P servers.

## How It Works

### The Port Forwarding Flow

```txt
1. Gluetun connects to ProtonVPN P2P server
          ↓
2. ProtonVPN assigns a forwarded port (e.g., 51820)
          ↓
3. Gluetun saves port to /tmp/gluetun/forwarded_port
          ↓
4. You configure qBittorrent to use this port
          ↓
5. Incoming connections now work through VPN tunnel
```

### Important Characteristics

- **Port changes** on every Gluetun restart/reconnection
- **Port is dynamic** - not static/permanent
- **Port persists** during a VPN session (until disconnect)
- **Manual update** required in qBittorrent when port changes
- **File location:** `/tmp/gluetun/forwarded_port` inside Gluetun container

## Initial Setup

### Step 1: Get ProtonVPN Credentials

1. **Log in** to ProtonVPN account at <https://account.protonvpn.com/>
2. Go to **Account** → **WireGuard configuration**
3. **Important:** Select a **P2P server** from the dropdown
   - Look for servers with "P2P" in the name
   - Recommended: Netherlands or Iceland servers
4. Click **Create** to generate configuration
5. **Download** the `.conf` file

### Step 2: Extract Credentials

Open the downloaded file (e.g., `protonvpn-NL-123.conf`):

```ini
[Interface]
PrivateKey = eF3k8mN...xYz123==
Address = 10.2.0.2/32
DNS = 10.2.0.1

[Peer]
PublicKey = jVp...890==
AllowedIPs = 0.0.0.0/0
Endpoint = 123.45.67.89:51820
```

Copy these values:

- **PrivateKey** → `WIREGUARD_PRIVATE_KEY` in `.env`
- **Address** → `WIREGUARD_ADDRESSES` in `.env`

### Step 3: Configure `.env` File

```bash
# Edit your .env file
nano .env
```

Add the credentials:

```bash
WIREGUARD_PRIVATE_KEY=eF3k8mN...xYz123==
WIREGUARD_ADDRESSES=10.2.0.2/32

# Optional: Force specific country (must be P2P)
SERVER_COUNTRIES=Netherlands
```

### Step 4: Start Stack

```bash
docker compose up -d
```

Wait 30-60 seconds for VPN connection and port forwarding to initialize.

## Port Forwarding Configuration

### Step 1: Get the Forwarded Port

```bash
docker exec gluetun cat /tmp/gluetun/forwarded_port
```

Example output: `51820`

**If the file is empty or returns an error:**

- Wait 30 more seconds (port forwarding takes time to establish)
- Check Gluetun logs: `docker logs gluetun | grep -i "port forward"`
- Verify you're using a P2P server: `docker logs gluetun | grep -i "server"`

### Step 2: Configure qBittorrent

1. **Access Web UI:** <http://localhost:8080>
   - Username: `admin`
   - Password: `docker logs qbittorrent 2>&1 | grep "temporary password"`

2. **Open Settings:**
   - Click the **gear icon** (⚙️) at the top
   - Or go to **Tools** → **Options**

3. **Configure Connection:**
   - Navigate to **Connection** tab
   - **Port used for incoming connections:** Enter the forwarded port (e.g., `51820`)
   - **Uncheck:** "Use UPnP / NAT-PMP port forwarding from my router"
   - **Random port on start:** Unchecked
   - Click **Save**

4. **Verify Connection:**
   - Look at the bottom status bar in qBittorrent
   - Wait 1-2 minutes
   - Should show a **green checkmark** or "Connectable"
   - If orange warning, wait or restart: `docker compose restart qbittorrent`

### Step 3: Test with a Torrent

1. Add a torrent with many seeds (popular Linux distro)
2. Check **Peers** tab - you should see incoming connections
3. Status should show as "Downloading" with active peers
4. Download speed should improve significantly

## Automated Port Updates

### The Challenge

ProtonVPN assigns a **new port** every time Gluetun restarts. You must update qBittorrent manually, or automate it.

### Option 1: Manual Check (Simple)

After restarting Gluetun:

```bash
# 1. Get new port
docker exec gluetun cat /tmp/gluetun/forwarded_port

# 2. Update in qBittorrent
# Go to Tools → Options → Connection → Set the new port
```

### Option 2: Automated Script (Recommended)

Create a script to automatically update qBittorrent:

```bash
#!/bin/bash
# File: update-qbt-port.sh
# Purpose: Automatically update qBittorrent listening port from Gluetun

set -e

# Configuration
QB_HOST="localhost:8080"
QB_USER="admin"
QB_PASS="your_password_here"  # Change this to your qBittorrent password

# Get forwarded port from Gluetun
echo "Checking Gluetun for forwarded port..."
FORWARDED_PORT=$(docker exec gluetun cat /tmp/gluetun/forwarded_port 2>/dev/null)

if [ -z "$FORWARDED_PORT" ]; then
    echo "❌ Error: Could not get forwarded port from Gluetun"
    echo "   Make sure Gluetun is running and port forwarding is enabled"
    exit 1
fi

echo "✓ Found forwarded port: $FORWARDED_PORT"

# Get current qBittorrent port
echo "Checking current qBittorrent port..."
COOKIE=$(curl -s -i --header "Referer: http://${QB_HOST}" \
    --data "username=${QB_USER}&password=${QB_PASS}" \
    "http://${QB_HOST}/api/v2/auth/login" | grep -i set-cookie | cut -d' ' -f2)

if [ -z "$COOKIE" ]; then
    echo "❌ Error: Failed to authenticate with qBittorrent"
    exit 1
fi

CURRENT_PORT=$(curl -s --cookie "$COOKIE" \
    "http://${QB_HOST}/api/v2/app/preferences" | \
    grep -o '"listen_port":[0-9]*' | cut -d':' -f2)

echo "Current qBittorrent port: $CURRENT_PORT"

# Update if different
if [ "$CURRENT_PORT" != "$FORWARDED_PORT" ]; then
    echo "Updating qBittorrent listening port to: $FORWARDED_PORT"

    curl -s -X POST "http://${QB_HOST}/api/v2/app/setPreferences" \
        --cookie "$COOKIE" \
        --data "json={\"listen_port\":${FORWARDED_PORT}}"

    echo "✓ Successfully updated qBittorrent port to: $FORWARDED_PORT"
    echo "  Please wait 1-2 minutes for connectivity check to complete"
else
    echo "✓ Port already correct: $FORWARDED_PORT"
fi
```

**Setup:**

```bash
# Save script
nano update-qbt-port.sh

# Make executable
chmod +x update-qbt-port.sh

# Edit with your qBittorrent password
nano update-qbt-port.sh  # Change QB_PASS line

# Run after Gluetun restarts
./update-qbt-port.sh
```

### Option 3: Cron Job (Advanced)

Run the script periodically to ensure port stays synchronized:

```bash
# Edit crontab
crontab -e

# Add line to check every 5 minutes
*/5 * * * * /path/to/update-qbt-port.sh >> /var/log/qbt-port-update.log 2>&1
```

### Option 4: Docker Compose with Restart Hook (Advanced)

Add a healthcheck that runs the script when Gluetun restarts - requires custom setup.

## Troubleshooting

### Port Forwarding Not Enabled

**Symptoms:**

- `/tmp/gluetun/forwarded_port` is empty
- Logs show no port forwarding messages

**Solutions:**

1. **Check docker-compose.yml:**

   ```yaml
   environment:
     - VPN_PORT_FORWARDING=on
     - VPN_PORT_FORWARDING_PROVIDER=protonvpn
   ```

2. **Verify P2P server:**

   ```bash
   docker logs gluetun | grep -i "server"
   ```

   Ensure connected to P2P-enabled country

3. **Check ProtonVPN plan:**
   - Port forwarding requires Plus or higher
   - Free plan does NOT support it

4. **Restart Gluetun:**

   ```bash
   docker compose restart gluetun
   docker logs -f gluetun | grep -i "port forward"
   ```

### qBittorrent Shows "Unconnectable"

**Symptoms:**

- Orange warning icon in qBittorrent status bar
- "Unconnectable" or "Firewalled" status

**Solutions:**

1. **Verify port match:**

   ```bash
   # Get Gluetun port
   docker exec gluetun cat /tmp/gluetun/forwarded_port

   # Compare with qBittorrent setting
   # Tools → Options → Connection → Port used for incoming connections
   ```

2. **Wait 2-3 minutes:**
   - ProtonVPN needs time to propagate port forwarding
   - Connectivity check runs periodically in qBittorrent

3. **Restart qBittorrent:**

   ```bash
   docker compose restart qbittorrent
   ```

4. **Test with active torrent:**
   - Add a torrent with many seeds
   - Check if peers can connect

5. **Verify VPN connection:**

   ```bash
   docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json
   ```

### Port Changes After Restart

**Symptoms:**

- Was connectable, now unconnectable
- Port in qBittorrent doesn't match Gluetun

**Solution:**

This is expected behavior. Update qBittorrent:

```bash
# 1. Get new port
NEW_PORT=$(docker exec gluetun cat /tmp/gluetun/forwarded_port)
echo "New port: $NEW_PORT"

# 2. Update qBittorrent manually or run script
./update-qbt-port.sh
```

### No Incoming Connections

**Symptoms:**

- Shows as connectable
- But no incoming peer connections in torrents

**Checks:**

1. **Verify port forwarding is active:**

   ```bash
   docker logs gluetun | grep -i "port forward"
   # Should see: "port forwarding enabled"
   ```

2. **Check torrent has enough peers:**
   - Need active peers for incoming connections
   - Try popular torrent with many seeds

3. **Wait for DHT/PEX:**
   - Takes 5-10 minutes for network to discover you
   - Be patient with new torrents

4. **Check firewall on host:**

   ```bash
   # macOS
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
   ```

### Gluetun Won't Start

**Symptoms:**

- Container keeps restarting
- Logs show connection errors

**Solutions:**

1. **Check credentials:**

   ```bash
   # Verify in .env file
   cat .env | grep WIREGUARD
   ```

2. **Verify WireGuard key format:**
   - Should be base64 string
   - Example: `eF3k8mN...xYz123==`

3. **Check server selection:**

   ```bash
   # If forcing specific country, ensure it has P2P servers
   cat .env | grep SERVER_COUNTRIES
   ```

4. **View detailed logs:**

   ```bash
   docker logs gluetun --tail 50
   ```

## Best Practices

### Port Management

1. **Document your port:** Keep track of current forwarded port
2. **Automate updates:** Use the script to update qBittorrent automatically
3. **Check after restarts:** Always verify port after restarting Gluetun
4. **Monitor connectivity:** Watch qBittorrent status bar for issues

### Server Selection

1. **Choose nearby P2P servers:** Reduces latency
2. **Avoid overloaded servers:** Switch if speeds are slow
3. **Test different locations:** Netherlands and Iceland are usually fast
4. **Lock to one country:** Use `SERVER_COUNTRIES` for consistency

### Performance

1. **Verify connectable:** Ensure qBittorrent shows green/connectable status
2. **Monitor incoming peers:** Should see incoming connections in active torrents
3. **Test with popular torrents:** Validate with high-seed torrents
4. **Adjust connection limits:** Increase if you have good bandwidth

### Security

1. **Never disable VPN:** Keep Gluetun kill-switch active
2. **Check VPN status:** Periodically verify you're connected
3. **Secure qBittorrent:** Change default password
4. **Monitor logs:** Watch for connection issues

## Quick Reference

### Essential Commands

```bash
# Get forwarded port
docker exec gluetun cat /tmp/gluetun/forwarded_port

# Check VPN status
docker exec gluetun wget -qO- https://protonwire.p3.pm/status/json

# View port forwarding logs
docker logs gluetun | grep -i "port forward"

# Check qBittorrent connectivity
# Look at bottom status bar in Web UI

# Restart services
docker compose restart gluetun
docker compose restart qbittorrent

# Update qBittorrent port (manual)
# Tools → Options → Connection → Set the forwarded port number

# Run port update script
./update-qbt-port.sh
```

### Port Forwarding Checklist

- [ ] ProtonVPN Plus subscription active
- [ ] WireGuard credentials in `.env`
- [ ] Selected P2P server (Netherlands, Iceland, Sweden, etc.)
- [ ] `VPN_PORT_FORWARDING=on` in docker-compose.yml
- [ ] Gluetun running and connected
- [ ] Forwarded port visible: `docker exec gluetun cat /tmp/gluetun/forwarded_port`
- [ ] Port configured in qBittorrent
- [ ] qBittorrent shows "Connectable"
- [ ] Incoming peer connections visible in active torrents

## Additional Resources

- **Gluetun Documentation:** <https://github.com/qdm12/gluetun/wiki>
- **ProtonVPN Support:** <https://protonvpn.com/support>
- **qBittorrent Wiki:** <https://github.com/qbittorrent/qBittorrent/wiki>
- **Port Forwarding Explained:** <https://protonvpn.com/support/port-forwarding/>

## Summary

**Automatic port forwarding with ProtonVPN provides:**

- ✅ Better download speeds
- ✅ More peer connections
- ✅ Improved private tracker performance
- ✅ Full connectivity through VPN tunnel
- ✅ Maintained privacy and security

**Key points to remember:**

- Requires ProtonVPN Plus plan
- Only works on P2P servers
- Port changes on each Gluetun restart
- Must update qBittorrent when port changes
- Automation script highly recommended
