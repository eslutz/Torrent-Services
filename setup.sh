#!/bin/bash

# Torrent Stack Setup Script
# This script creates the necessary directory structure and validates configuration

set -e  # Exit on error

echo "=========================================="
echo "Torrent Stack Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
  echo "⚠️  Warning: .env file not found!"
  echo ""
  echo "Creating .env from .env.example..."
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
  else
    echo "❌ Error: .env.example not found!"
    exit 1
  fi
fi

# Load .env
source .env

# Check VPN mode and provider
USE_VPN=${USE_VPN:-vpn}
VPN_SERVICE_PROVIDER=${VPN_SERVICE_PROVIDER:-mullvad}
VPN_TYPE=${VPN_TYPE:-wireguard}

echo "VPN Mode: $USE_VPN"
echo "VPN Provider: $VPN_SERVICE_PROVIDER"
echo "VPN Protocol: $VPN_TYPE"
echo ""

# Validate based on VPN mode
if [ "$USE_VPN" == "vpn" ]; then
  echo "VPN mode enabled - validating credentials..."
  echo ""

  # Validate based on provider and protocol
  case "$VPN_SERVICE_PROVIDER" in
    mullvad)
      if [ "$VPN_TYPE" == "wireguard" ]; then
        if [ -z "$WIREGUARD_PRIVATE_KEY" ] || [ "$WIREGUARD_PRIVATE_KEY" == "your_private_key_here" ]; then
          echo "❌ Error: WIREGUARD_PRIVATE_KEY not set in .env file!"
          echo ""
          echo "To use Mullvad with Wireguard:"
          echo "  1. Sign up at: https://mullvad.net/"
          echo "  2. Get WireGuard config: https://mullvad.net/account/wireguard-config"
          echo "  3. Edit .env file and set:"
          echo "     - WIREGUARD_PRIVATE_KEY"
          echo "     - WIREGUARD_ADDRESSES"
          echo ""
          exit 1
        fi
        if [ -z "$WIREGUARD_ADDRESSES" ] || [ "$WIREGUARD_ADDRESSES" == "10.x.x.x/32" ]; then
          echo "❌ Error: WIREGUARD_ADDRESSES not set in .env file!"
          echo "   Get it from: https://mullvad.net/account/wireguard-config"
          echo ""
          exit 1
        fi
      else
        if [ -z "$OPENVPN_USER" ]; then
          echo "❌ Error: OPENVPN_USER not set for Mullvad OpenVPN"
          echo "   Use your Mullvad account number"
          exit 1
        fi
      fi
      echo "✓ Mullvad credentials found"
      ;;

    nordvpn|protonvpn|surfshark|expressvpn|ipvanish|cyberghost|torguard|windscribe)
      if [ "$VPN_TYPE" == "wireguard" ]; then
        if [ -z "$WIREGUARD_PRIVATE_KEY" ] || [ "$WIREGUARD_PRIVATE_KEY" == "your_private_key_here" ]; then
          echo "❌ Error: WIREGUARD_PRIVATE_KEY not set in .env file!"
          echo ""
          echo "To use $VPN_SERVICE_PROVIDER with Wireguard:"
          echo "  1. Check your VPN provider's account settings"
          echo "  2. Generate/download Wireguard configuration"
          echo "  3. Edit .env file and set:"
          echo "     - WIREGUARD_PRIVATE_KEY"
          echo "     - WIREGUARD_ADDRESSES"
          echo ""
          exit 1
        fi
        if [ -z "$WIREGUARD_ADDRESSES" ]; then
          echo "❌ Error: WIREGUARD_ADDRESSES not set in .env file!"
          exit 1
        fi
      else
        if [ -z "$OPENVPN_USER" ] || [ -z "$OPENVPN_PASSWORD" ]; then
          echo "❌ Error: OPENVPN_USER and OPENVPN_PASSWORD required for $VPN_SERVICE_PROVIDER"
          echo ""
          echo "To use $VPN_SERVICE_PROVIDER with OpenVPN:"
          echo "  1. Login to your VPN provider account"
          echo "  2. Find your OpenVPN credentials"
          echo "  3. Edit .env file and set:"
          echo "     - OPENVPN_USER"
          echo "     - OPENVPN_PASSWORD"
          echo ""
          exit 1
        fi
      fi
      echo "✓ $VPN_SERVICE_PROVIDER credentials found"
      ;;

    "private internet access"|pia)
      # PIA supports both Wireguard and OpenVPN
      if [ "$VPN_TYPE" == "wireguard" ]; then
        if [ -z "$WIREGUARD_PRIVATE_KEY" ]; then
          echo "❌ Error: WIREGUARD_PRIVATE_KEY required for PIA Wireguard"
          exit 1
        fi
        if [ -z "$WIREGUARD_ADDRESSES" ]; then
          echo "❌ Error: WIREGUARD_ADDRESSES required for PIA Wireguard"
          exit 1
        fi
      else
        if [ -z "$OPENVPN_USER" ] || [ -z "$OPENVPN_PASSWORD" ]; then
          echo "❌ Error: OPENVPN_USER and OPENVPN_PASSWORD required for PIA OpenVPN"
          exit 1
        fi
      fi
      echo "✓ Private Internet Access credentials found"
      ;;

    *)
      echo "⚠️  Warning: Unknown VPN provider: $VPN_SERVICE_PROVIDER"
      echo ""
      echo "Supported providers include:"
      echo "  - mullvad, nordvpn, protonvpn, surfshark"
      echo "  - private internet access, expressvpn, ipvanish"
      echo "  - cyberghost, torguard, windscribe, and more"
      echo ""
      echo "Full list: https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers"
      echo ""
      echo "Continuing setup, but verify your VPN_SERVICE_PROVIDER is correct..."
      echo ""
      ;;
  esac
  echo ""

elif [ "$USE_VPN" == "no-vpn" ]; then
  echo "⚠️  WARNING: VPN disabled - your real IP will be exposed!"
  echo ""
  echo "   This mode should only be used for:"
  echo "   - Local development/testing"
  echo "   - Legal content only"
  echo "   - When behind another VPN"
  echo ""
  echo "   For production use, strongly consider enabling VPN."
  echo ""
  read -p "Continue without VPN? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Setup cancelled. To enable VPN:"
    echo "  1. Set USE_VPN=vpn in .env"
    echo "  2. Add Mullvad credentials to .env"
    echo "  3. Run ./setup.sh again"
    exit 0
  fi
  echo ""
else
  echo "❌ Error: Invalid USE_VPN value: '$USE_VPN'"
  echo "   Must be either 'vpn' or 'no-vpn'"
  exit 1
fi

# Get PUID/PGID
PUID=${PUID:-$(id -u)}
PGID=${PGID:-$(id -g)}

# Data directory (default: data)
DATA_DIR=${DATA_DIR:-data}

echo "Using user ID: $PUID"
echo "Using group ID: $PGID"
echo "Using data directory: $DATA_DIR"
echo ""

# Create directory structure
echo "Creating directory structure..."

mkdir -p "$DATA_DIR/tv" "$DATA_DIR/movies" "$DATA_DIR/downloads/torrents/incomplete" "$DATA_DIR/downloads/torrents/complete" "$DATA_DIR/downloads/usenet"
mkdir -p docs
mkdir -p gluetun/config sonarr/config radarr/config qbittorrent/config prowlarr/config bazarr/config

echo "✓ Directories created"
echo ""

# Set permissions
echo "Setting permissions..."
if command -v sudo &> /dev/null; then
  sudo chown -R $PUID:$PGID "$DATA_DIR" gluetun/ sonarr/ radarr/ qbittorrent/ prowlarr/ bazarr/
  sudo chmod -R 755 "$DATA_DIR"
else
  chown -R $PUID:$PGID "$DATA_DIR" gluetun/ sonarr/ radarr/ qbittorrent/ prowlarr/ bazarr/
  chmod -R 755 "$DATA_DIR"
fi

echo "✓ Permissions set"
echo ""

# Check Docker
echo "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
  echo "❌ Error: Docker is not installed!"
  echo "   Install from: https://docs.docker.com/get-docker/"
  exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
  echo "❌ Error: Docker Compose is not installed!"
  echo "   Install from: https://docs.docker.com/compose/install/"
  exit 1
fi

echo "✓ Docker is installed"
echo ""

# Display directory tree if available
if command -v tree &> /dev/null; then
  echo "Directory structure:"
  tree -L 3 -d -I 'config' "$DATA_DIR"
  echo ""
fi

echo "=========================================="
echo "✓ SETUP COMPLETE!"
echo "=========================================="
echo ""

if [ "$USE_VPN" == "vpn" ]; then
  echo "Next steps (VPN Mode - $VPN_SERVICE_PROVIDER):"
  echo ""
  echo "1. Review your configuration:"
  echo "   cat .env"
  echo ""
  echo "2. Start the containers with VPN:"
  echo "   docker-compose --profile vpn up -d"
  echo ""
  echo "3. Check VPN connection:"
  echo "   docker exec gluetun wget -qO- https://am.i.mullvad.net/connected"
  echo "   (Note: This works for all providers, not just Mullvad)"
  echo ""
  echo "4. Access the web interfaces:"
  echo "   - Sonarr:      http://localhost:8989"
  echo "   - Radarr:      http://localhost:7878"
  echo "   - qBittorrent: http://localhost:8080"
  echo "   - Prowlarr:    http://localhost:9696"
  echo "   - Bazarr:      http://localhost:6767"
  echo ""
  echo "5. Get qBittorrent password:"
  echo "   docker logs qbittorrent 2>&1 | grep 'temporary password'"
  echo ""
  echo "6. Configure Sonarr/Radarr download client:"
  echo "   Settings → Download Clients → Add → qBittorrent"
  echo "   Host: gluetun"
  echo "   Port: 8080"
  echo "   (Use 'gluetun' hostname because qBittorrent routes through VPN)"
  echo ""
  echo "🔒 Security: All torrent traffic routes through $VPN_SERVICE_PROVIDER VPN"
else
  echo "Next steps (No-VPN Mode):"
  echo ""
  echo "1. Review your configuration:"
  echo "   cat .env"
  echo ""
  echo "2. Start the containers without VPN:"
  echo "   docker-compose --profile no-vpn up -d"
  echo ""
  echo "3. Access the web interfaces:"
  echo "   - Sonarr:      http://localhost:8989"
  echo "   - Radarr:      http://localhost:7878"
  echo "   - qBittorrent: http://localhost:8080"
  echo "   - Prowlarr:    http://localhost:9696"
  echo "   - Bazarr:      http://localhost:6767"
  echo ""
  echo "4. Get qBittorrent password:"
  echo "   docker logs qbittorrent 2>&1 | grep 'temporary password'"
  echo ""
  echo "5. Configure Sonarr/Radarr download client:"
  echo "   Settings → Download Clients → Add → qBittorrent"
  echo "   Host: qbittorrent"
  echo "   Port: 8080"
  echo "   (Use 'qbittorrent' hostname for direct connection)"
  echo ""
  echo "⚠️  WARNING: Your real IP is exposed when torrenting!"
fi
echo ""
echo "📚 Documentation: See docs/ directory for detailed guides"
echo ""
echo "=========================================="
