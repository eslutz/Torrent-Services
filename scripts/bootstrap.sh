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
#   - Adds sample indexers to Prowlarr (1337x, 1337x Tor)
#   - Optionally starts monitoring exporters (set ENABLE_MONITORING_PROFILE=true)
#
# Usage:
#   ./scripts/bootstrap.sh
#
# Requirements:
#   - All containers must be running and healthy
#   - .env file must exist with QBIT_USER, QBIT_PASS, and optional credentials
#   - curl, jq, grep, and docker must be installed
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

# Escape values so they can be safely written to .env
escape_env_value() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    echo "$value"
}

# Insert or update a key=value pair inside .env
upsert_env_var() {
    local key="$1"
    local value_escaped
    value_escaped=$(escape_env_value "$2")

    if grep -q "^${key}=" "$ENV_FILE"; then
        awk -v k="$key" -v v="$value_escaped" 'BEGIN{q="\""} $0 ~ "^"k"=" {print k "=" q v q; next} {print}' "$ENV_FILE" > "${ENV_FILE}.tmp"
        mv "${ENV_FILE}.tmp" "$ENV_FILE"
    else
        printf "\\n%s=\"%s\"\\n" "$key" "$value_escaped" >> "$ENV_FILE"
    fi
}

persist_env_var() {
    local key="$1"
    local value="$2"
    if [ -z "$value" ]; then
        log_warning "Skipping ${key} persistence - value is empty"
        return 0
    fi
    upsert_env_var "$key" "$value"
    log_success "Saved ${key} to .env"
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
# API Key Extraction
# =============================================================================

get_sonarr_api_key() {
    local config_file="$PROJECT_DIR/config/sonarr/config.xml"
    if [ -f "$config_file" ]; then
        grep -oP '(?<=<ApiKey>)[^<]+' "$config_file" 2>/dev/null || echo ""
    fi
}

get_radarr_api_key() {
    local config_file="$PROJECT_DIR/config/radarr/config.xml"
    if [ -f "$config_file" ]; then
        grep -oP '(?<=<ApiKey>)[^<]+' "$config_file" 2>/dev/null || echo ""
    fi
}

get_prowlarr_api_key() {
    local config_file="$PROJECT_DIR/config/prowlarr/config.xml"
    if [ -f "$config_file" ]; then
        grep -oP '(?<=<ApiKey>)[^<]+' "$config_file" 2>/dev/null || echo ""
    fi
}

get_bazarr_api_key() {
    local config_file="$PROJECT_DIR/config/bazarr/config/config.yaml"
    if [ -f "$config_file" ]; then
        grep -E '^\s+apikey:' "$config_file" | head -1 | awk '{print $2}' | tr -d "'" | tr -d '"' 2>/dev/null || echo ""
    fi
}

# =============================================================================
# Connection Check Functions
# =============================================================================

check_prowlarr_app_exists() {
    local app_name="$1"
    local result
    result=$(curl -s "http://localhost:9696/api/v1/applications" \
        -H "X-Api-Key: $PROWLARR_API_KEY" | jq -r ".[] | select(.name == \"$app_name\") | .name" 2>/dev/null)
    [ "$result" = "$app_name" ]
}

check_download_client_exists() {
    local port="$1"
    local api_key="$2"
    local client_name="$3"
    local result
    result=$(curl -s "http://localhost:$port/api/v3/downloadclient" \
        -H "X-Api-Key: $api_key" | jq -r ".[] | select(.name == \"$client_name\") | .name" 2>/dev/null)
    [ "$result" = "$client_name" ]
}

check_prowlarr_indexer_exists() {
    local indexer_name="$1"
    local result
    result=$(curl -s "http://localhost:9696/api/v1/indexer" \
        -H "X-Api-Key: $PROWLARR_API_KEY" | jq -r ".[] | select(.name == \"$indexer_name\") | .name" 2>/dev/null)
    [ "$result" = "$indexer_name" ]
}

# =============================================================================
# Configuration Functions
# =============================================================================

configure_prowlarr_sonarr() {
    if check_prowlarr_app_exists "Sonarr"; then
        log_success "Prowlarr → Sonarr already configured"
        return 0
    fi

    log_info "Configuring Prowlarr → Sonarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:9696/api/v1/applications" \
        -H "X-Api-Key: $PROWLARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Sonarr",
            "syncLevel": "fullSync",
            "implementation": "Sonarr",
            "configContract": "SonarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://sonarr:8989"},
                {"name": "apiKey", "value": "'"$SONARR_API_KEY"'"},
                {"name": "syncCategories", "value": [5000, 5010, 5020, 5030, 5040, 5045, 5050]}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Prowlarr → Sonarr configured"
    else
        log_error "Failed to configure Prowlarr → Sonarr (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_prowlarr_radarr() {
    if check_prowlarr_app_exists "Radarr"; then
        log_success "Prowlarr → Radarr already configured"
        return 0
    fi

    log_info "Configuring Prowlarr → Radarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:9696/api/v1/applications" \
        -H "X-Api-Key: $PROWLARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Radarr",
            "syncLevel": "fullSync",
            "implementation": "Radarr",
            "configContract": "RadarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://radarr:7878"},
                {"name": "apiKey", "value": "'"$RADARR_API_KEY"'"},
                {"name": "syncCategories", "value": [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060]}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Prowlarr → Radarr configured"
    else
        log_error "Failed to configure Prowlarr → Radarr (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_sonarr_qbittorrent() {
    if check_download_client_exists "8989" "$SONARR_API_KEY" "qBittorrent"; then
        log_success "Sonarr → qBittorrent already configured"
        return 0
    fi

    log_info "Configuring Sonarr → qBittorrent..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8989/api/v3/downloadclient" \
        -H "X-Api-Key: $SONARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "qBittorrent",
            "enable": true,
            "protocol": "torrent",
            "priority": 1,
            "removeCompletedDownloads": true,
            "removeFailedDownloads": true,
            "implementation": "QBittorrent",
            "configContract": "QBittorrentSettings",
            "fields": [
                {"name": "host", "value": "gluetun"},
                {"name": "port", "value": 8080},
                {"name": "useSsl", "value": false},
                {"name": "username", "value": "'"$QBIT_USER"'"},
                {"name": "password", "value": "'"$QBIT_PASS"'"},
                {"name": "tvCategory", "value": "tv"},
                {"name": "recentTvPriority", "value": 0},
                {"name": "olderTvPriority", "value": 0},
                {"name": "initialState", "value": 0},
                {"name": "sequentialOrder", "value": false},
                {"name": "firstAndLast", "value": false}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Sonarr → qBittorrent configured"
    else
        log_error "Failed to configure Sonarr → qBittorrent (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_radarr_qbittorrent() {
    if check_download_client_exists "7878" "$RADARR_API_KEY" "qBittorrent"; then
        log_success "Radarr → qBittorrent already configured"
        return 0
    fi

    log_info "Configuring Radarr → qBittorrent..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:7878/api/v3/downloadclient" \
        -H "X-Api-Key: $RADARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "qBittorrent",
            "enable": true,
            "protocol": "torrent",
            "priority": 1,
            "removeCompletedDownloads": true,
            "removeFailedDownloads": true,
            "implementation": "QBittorrent",
            "configContract": "QBittorrentSettings",
            "fields": [
                {"name": "host", "value": "gluetun"},
                {"name": "port", "value": 8080},
                {"name": "useSsl", "value": false},
                {"name": "username", "value": "'"$QBIT_USER"'"},
                {"name": "password", "value": "'"$QBIT_PASS"'"},
                {"name": "movieCategory", "value": "movies"},
                {"name": "recentMoviePriority", "value": 0},
                {"name": "olderMoviePriority", "value": 0},
                {"name": "initialState", "value": 0},
                {"name": "sequentialOrder", "value": false},
                {"name": "firstAndLast", "value": false}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Radarr → qBittorrent configured"
    else
        log_error "Failed to configure Radarr → qBittorrent (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_bazarr_sonarr() {
    log_info "Configuring Bazarr → Sonarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X PATCH "http://localhost:6767/api/system/settings" \
        -H "X-API-KEY: $BAZARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "sonarr": {
                "ip": "sonarr",
                "port": 8989,
                "base_url": "",
                "ssl": false,
                "apikey": "'"$SONARR_API_KEY"'",
                "full_update": "Daily",
                "full_update_day": 6,
                "full_update_hour": 4,
                "only_monitored": true,
                "series_sync": 60,
                "excluded_tags": [],
                "excluded_series_types": []
            },
            "general": {
                "use_sonarr": true
            }
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
        log_success "Bazarr → Sonarr configured"
    else
        log_error "Failed to configure Bazarr → Sonarr (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_bazarr_radarr() {
    log_info "Configuring Bazarr → Radarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X PATCH "http://localhost:6767/api/system/settings" \
        -H "X-API-KEY: $BAZARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "radarr": {
                "ip": "radarr",
                "port": 7878,
                "base_url": "",
                "ssl": false,
                "apikey": "'"$RADARR_API_KEY"'",
                "full_update": "Daily",
                "full_update_day": 6,
                "full_update_hour": 4,
                "only_monitored": true,
                "movies_sync": 60,
                "excluded_tags": []
            },
            "general": {
                "use_radarr": true
            }
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
        log_success "Bazarr → Radarr configured"
    else
        log_error "Failed to configure Bazarr → Radarr (HTTP $http_code)"
        echo "$response" | head -n -1
        return 1
    fi
}

configure_bazarr_providers() {
    log_info "Configuring Bazarr subtitle providers..."

    local providers='["podnapisi"]'
    local addic7ed_config='{}'
    local opensubtitlescom_config='{}'

    # Add Addic7ed if credentials are provided
    if [ -n "$ADDIC7ED_USERNAME" ] && [ -n "$ADDIC7ED_PASSWORD" ]; then
        providers='["addic7ed", "podnapisi"]'
        addic7ed_config='{
            "username": "'"$ADDIC7ED_USERNAME"'",
            "password": "'"$ADDIC7ED_PASSWORD"'",
            "cookies": "'"${ADDIC7ED_COOKIES:-}"'"
        }'
        log_info "  - Addic7ed: enabled"
    fi

    # Add OpenSubtitles.com if credentials are provided
    if [ -n "$OPENSUBTITLESCOM_USERNAME" ] && [ -n "$OPENSUBTITLESCOM_PASSWORD" ]; then
        if [ "$providers" = '["podnapisi"]' ]; then
            providers='["opensubtitlescom", "podnapisi"]'
        else
            providers='["addic7ed", "opensubtitlescom", "podnapisi"]'
        fi
        opensubtitlescom_config='{
            "username": "'"$OPENSUBTITLESCOM_USERNAME"'",
            "password": "'"$OPENSUBTITLESCOM_PASSWORD"'",
            "use_hash": true,
            "include_ai_translated": true
        }'
        log_info "  - OpenSubtitles.com: enabled"
    fi

    log_info "  - Podnapisi: enabled (no credentials needed)"

    local response
    response=$(curl -s -w "\n%{http_code}" -X PATCH "http://localhost:6767/api/system/settings" \
        -H "X-API-KEY: $BAZARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "general": {
                "enabled_providers": '"$providers"'
            },
            "addic7ed": '"$addic7ed_config"',
            "opensubtitlescom": '"$opensubtitlescom_config"'
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
        log_success "Bazarr subtitle providers configured"
    else
        log_warning "Failed to configure Bazarr providers (HTTP $http_code) - may need manual setup"
    fi
}

configure_prowlarr_indexer_1337x() {
    if check_prowlarr_indexer_exists "1337x"; then
        log_success "Prowlarr indexer '1337x' already configured"
        return 0
    fi

    log_info "Adding Prowlarr indexer: 1337x..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:9696/api/v1/indexer" \
        -H "X-Api-Key: $PROWLARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "1337x",
            "definitionName": "1337x",
            "enable": true,
            "redirect": false,
            "supportsRss": true,
            "supportsSearch": true,
            "supportsRedirect": false,
            "appProfileId": 1,
            "priority": 25,
            "fields": [
                {"name": "definitionFile", "value": "1337x"}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Prowlarr indexer '1337x' added"
    else
        log_warning "Failed to add 1337x indexer (HTTP $http_code)"
    fi
}

configure_prowlarr_indexer_1337x_tor() {
    if check_prowlarr_indexer_exists "1337x (Tor)"; then
        log_success "Prowlarr indexer '1337x (Tor)' already configured"
        return 0
    fi

    # Check if custom definition exists
    if [ ! -f "$PROJECT_DIR/config/prowlarr/Definitions/Custom/1337x-tor.yml" ]; then
        log_warning "Custom 1337x-tor.yml not found, skipping Tor indexer"
        return 0
    fi

    log_info "Adding Prowlarr indexer: 1337x (Tor)..."

    # First, add a Tor proxy to Prowlarr
    local proxy_exists
    proxy_exists=$(curl -s "http://localhost:9696/api/v1/indexerProxy" \
        -H "X-Api-Key: $PROWLARR_API_KEY" | jq -r '.[] | select(.name == "Tor") | .name' 2>/dev/null)

    if [ "$proxy_exists" != "Tor" ]; then
        log_info "  Adding Tor proxy..."
        curl -s -X POST "http://localhost:9696/api/v1/indexerProxy" \
            -H "X-Api-Key: $PROWLARR_API_KEY" \
            -H "Content-Type: application/json" \
            -d '{
                "name": "Tor",
                "implementation": "Socks5",
                "configContract": "Socks5Settings",
                "fields": [
                    {"name": "host", "value": "tor-proxy"},
                    {"name": "port", "value": 9050},
                    {"name": "username", "value": ""},
                    {"name": "password", "value": ""}
                ],
                "tags": []
            }' > /dev/null
    fi

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:9696/api/v1/indexer" \
        -H "X-Api-Key: $PROWLARR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "1337x (Tor)",
            "definitionName": "1337x-tor",
            "enable": true,
            "redirect": false,
            "supportsRss": true,
            "supportsSearch": true,
            "supportsRedirect": false,
            "appProfileId": 1,
            "priority": 25,
            "fields": [
                {"name": "definitionFile", "value": "1337x-tor"}
            ],
            "tags": []
        }')

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
        log_success "Prowlarr indexer '1337x (Tor)' added"
    else
        log_warning "Failed to add 1337x (Tor) indexer (HTTP $http_code)"
    fi
}

sync_prowlarr_indexers() {
    log_info "Triggering Prowlarr indexer sync to apps..."

    curl -s -X POST "http://localhost:9696/api/v1/applicationsync" \
        -H "X-Api-Key: $PROWLARR_API_KEY" > /dev/null

    log_success "Prowlarr indexer sync triggered"
}

start_monitoring_profile() {
    if ! is_truthy "${ENABLE_MONITORING_PROFILE:-false}"; then
        log_info "Monitoring profile disabled (set ENABLE_MONITORING_PROFILE=true in .env to enable)"
        return 0
    fi

    # Verify API keys are available (required by exporters)
    if [ -z "$SONARR_API_KEY" ] || [ -z "$RADARR_API_KEY" ] || [ -z "$PROWLARR_API_KEY" ] || [ -z "$BAZARR_API_KEY" ]; then
        log_error "Cannot start monitoring exporters - API keys not available"
        log_error "Ensure Sonarr, Radarr, and Prowlarr API keys are set in .env"
        return 1
    fi

    log_info "Starting monitoring exporters via docker compose profile..."

    # Start monitoring containers
    if (cd "$PROJECT_DIR" && docker compose --profile monitoring up -d qbittorrent-exporter scraparr 2>&1); then
        log_success "Monitoring exporters started successfully"

        # Wait a few seconds for exporters to initialize
        sleep 5

        # Verify exporters are running
        local failed=0
        for service in qbittorrent-exporter scraparr; do
            if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
                log_success "  ✓ $service is running"
            else
                log_error "  ✗ $service failed to start"
                failed=1
            fi
        done

        if [ $failed -eq 0 ]; then
            echo ""
            log_info "Prometheus scrape targets:"
            log_info "  - qBittorrent: http://192.168.50.100:8090/metrics"
            log_info "  - Scraparr:    http://192.168.50.100:7100/metrics"
        fi
    else
        log_error "Failed to start monitoring exporters"
        log_warning "Check logs with: docker compose --profile monitoring logs"
        return 1
    fi
}

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

    ENABLE_MONITORING_PROFILE=${ENABLE_MONITORING_PROFILE:-false}

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
    wait_for_service "Bazarr" "http://localhost:6767/ping"
    wait_for_service "qBittorrent" "http://localhost:8080"

    log_section "Authentication Configuration"

    log_info "Services use built-in authentication (Forms-based login)"
    log_info "Default credentials are set on first access to each service"
    log_info "Recommended: Set strong passwords immediately after first login"
    log_info ""
    log_info "Service URLs:"
    log_info "  • Prowlarr:    http://localhost:9696"
    log_info "  • Sonarr:      http://localhost:8989"
    log_info "  • Radarr:      http://localhost:7878"
    log_info "  • Bazarr:      http://localhost:6767"
    log_info "  • qBittorrent: http://localhost:8080"

    log_section "Reading API Keys"

    SONARR_API_KEY=$(get_sonarr_api_key)
    RADARR_API_KEY=$(get_radarr_api_key)
    PROWLARR_API_KEY=$(get_prowlarr_api_key)
    BAZARR_API_KEY=$(get_bazarr_api_key)

    if [ -z "$SONARR_API_KEY" ]; then
        log_error "Could not read Sonarr API key from config"
        exit 1
    fi
    log_success "Sonarr API key: ${SONARR_API_KEY:0:8}..."

    if [ -z "$RADARR_API_KEY" ]; then
        log_error "Could not read Radarr API key from config"
        exit 1
    fi
    log_success "Radarr API key: ${RADARR_API_KEY:0:8}..."

    if [ -z "$PROWLARR_API_KEY" ]; then
        log_error "Could not read Prowlarr API key from config"
        exit 1
    fi
    log_success "Prowlarr API key: ${PROWLARR_API_KEY:0:8}..."

    if [ -z "$BAZARR_API_KEY" ]; then
        log_error "Could not read Bazarr API key from config"
        exit 1
    fi
    log_success "Bazarr API key: ${BAZARR_API_KEY:0:8}..."

    log_section "Persisting API Keys to .env"

    persist_env_var "QBIT_USER" "$QBIT_USER"
    persist_env_var "QBIT_PASS" "$QBIT_PASS"
    persist_env_var "SONARR_API_KEY" "$SONARR_API_KEY"
    persist_env_var "RADARR_API_KEY" "$RADARR_API_KEY"
    persist_env_var "PROWLARR_API_KEY" "$PROWLARR_API_KEY"
    persist_env_var "BAZARR_API_KEY" "$BAZARR_API_KEY"

    log_section "Configuring Prowlarr Applications"

    configure_prowlarr_sonarr
    configure_prowlarr_radarr

    log_section "Configuring Download Clients"

    configure_sonarr_qbittorrent
    configure_radarr_qbittorrent

    log_section "Configuring Bazarr"

    configure_bazarr_sonarr
    configure_bazarr_radarr
    configure_bazarr_providers

    log_section "Configuring Prowlarr Indexers"

    configure_prowlarr_indexer_1337x
    configure_prowlarr_indexer_1337x_tor

    log_section "Syncing Indexers"

    sync_prowlarr_indexers

    log_section "Monitoring Exporters"

    start_monitoring_profile

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
    if is_truthy "${ENABLE_MONITORING_PROFILE:-false}"; then
        echo "Monitoring exporters (for Prometheus):"
        echo "  • qBittorrent: http://192.168.50.100:8090/metrics"
        echo "  • Scraparr:    http://192.168.50.100:7100/metrics"
        echo ""
    fi
    echo "Configuration saved to: $ENV_FILE"
    echo ""
}

# Run main function
main "$@"
