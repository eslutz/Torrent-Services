#!/bin/bash

# =============================================================================
# Torrent Services Bootstrap Script
# =============================================================================
# This script configures all inter-service connections after containers start.
# It reads auto-generated API keys from each app and creates connections via API.
#
# Features:
#   - Extracts API keys from config files and saves them to .env
#   - Configures Prowlarr → Sonarr/Radarr application connections
#   - Configures Sonarr/Radarr → qBittorrent download client connections
#   - Configures Bazarr → Sonarr/Radarr integrations
#
# Usage:
#   ./scripts/bootstrap.sh
#
# Requirements:
#   - All containers must be running and healthy
#   - .env file must exist with QBIT_USER, QBIT_PASS, and optional credentials
#   - curl, jq, grep, sed, and docker must be installed
#
# Compatibility:
#   - macOS and Linux compatible (uses portable sed/grep patterns)
#   - Avoids GNU-specific flags (grep -P, head -n -1)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory (for relative paths)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

is_truthy() {
    case "$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

# Check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed."
        exit 1
    fi
}

# Wait for a service to be healthy
wait_for_service() {
    local name="$1"
    local url="$2"
    local max_attempts=30
    local attempt=1

    log_info "Waiting for $name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|401\|302"; then
            log_success "$name is ready"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "$name failed to become ready after $max_attempts attempts"
    return 1
}



# =============================================================================
# Configuration Functions
# =============================================================================



# =============================================================================
# Main Execution
# =============================================================================

main() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Torrent Services Bootstrap Script                    ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check required commands
    check_command "curl"
    check_command "jq"
    check_command "grep"
    check_command "docker"

    # Load environment variables
    if [ -f "$PROJECT_DIR/.env" ]; then
        log_info "Loading environment variables from .env..."
        set -a
        # shellcheck source=/dev/null
        source "$PROJECT_DIR/.env"
        set +a
    else
        log_error ".env file not found at $PROJECT_DIR/.env"
        exit 1
    fi

    # Validate required environment variables
    if [ -z "$QBIT_USER" ] || [ -z "$QBIT_PASS" ]; then
        log_error "QBIT_USER and QBIT_PASS must be set in .env"
        log_info "These are used for qBittorrent API access by Sonarr/Radarr"
        exit 1
    fi

    log_section "Waiting for Services"

    wait_for_service "Prowlarr" "http://localhost:9696/ping"
    wait_for_service "Sonarr" "http://localhost:8989/ping"
    wait_for_service "Radarr" "http://localhost:7878/ping"
// ...existing code...
    wait_for_service "Bazarr" "http://localhost:6767/ping"
    wait_for_service "qBittorrent" "http://localhost:8080"

    log_section "Extracting API Keys"

    log_info "Running API key extraction script..."
    if python3 "$SCRIPT_DIR/setup/extract_api_keys.py"; then
        log_success "API keys extracted and saved to .env"
        # Reload .env to get the new keys
        set -a
        source "$PROJECT_DIR/.env"
        set +a
    else
        log_error "Failed to extract API keys"
        exit 1
    fi

    log_section "Configuring qBittorrent"

    log_info "Running qBittorrent setup script..."
    if python3 "$SCRIPT_DIR/setup/setup_qbittorrent.py"; then
        log_success "qBittorrent setup completed"
    else
        log_error "qBittorrent setup failed"
        exit 1
    fi

    log_section "Configuring Prowlarr"

    log_info "Running Prowlarr setup script..."
    if python3 "$SCRIPT_DIR/setup/setup_prowlarr.py"; then
        log_success "Prowlarr setup completed"
    else
        log_error "Prowlarr setup failed"
        exit 1
    fi

    log_section "Configuring Sonarr"

    log_info "Running Sonarr setup script..."
    if python3 "$SCRIPT_DIR/setup/setup_sonarr.py"; then
        log_success "Sonarr setup completed"
    else
        log_error "Sonarr setup failed"
        exit 1
    fi

    log_section "Configuring Radarr"

    log_info "Running Radarr setup script..."
    if python3 "$SCRIPT_DIR/setup/setup_radarr.py"; then
        log_success "Radarr setup completed"
    else
        log_error "Radarr setup failed"
        exit 1
    fi

    log_section "Configuring Bazarr"

    log_info "Running Bazarr setup script..."
    if python3 "$SCRIPT_DIR/setup/setup_bazarr.py"; then
        log_success "Bazarr setup completed"
    else
        log_error "Bazarr setup failed"
        exit 1
    fi

    if is_truthy "$ENABLE_MONITORING_PROFILE"; then
        log_section "Starting Monitoring Stack"
        log_info "ENABLE_MONITORING_PROFILE is set to true"
        log_info "Starting exporters..."
        docker compose --profile monitoring up -d
        log_success "Monitoring stack started"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Bootstrap Complete!                       ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Service URLs:"
    echo "  • Prowlarr:    http://192.168.50.100:9696 (Indexer management)"
    echo "  • Sonarr:      http://192.168.50.100:8989 (TV shows)"
    echo "  • Radarr:      http://192.168.50.100:7878 (Movies)"
    echo "  • Bazarr:      http://192.168.50.100:6767 (Subtitles)"
    echo "  • qBittorrent: http://192.168.50.100:8080 (Downloads)"
    echo ""
    echo "Configuration saved to: $ENV_FILE"
    echo ""
}

# Run main function
main "$@"
