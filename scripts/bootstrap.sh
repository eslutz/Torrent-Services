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
# qBittorrent Credential Management
# =============================================================================

get_qbittorrent_temp_password() {
    # Extract temporary password from qBittorrent logs if it exists
    # Checks entire log to handle cases where bootstrap is run long after container startup
    docker logs qbittorrent 2>&1 | grep "temporary password" | tail -1 | sed -E 's/.*temporary password is provided for this session: ([A-Za-z0-9]+).*/\1/' || echo ""
}

check_qbittorrent_auth() {
    local user="$1"
    local pass="$2"
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8080/api/v2/auth/login" \
        --data-urlencode "username=$user" \
        --data-urlencode "password=$pass")
    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')
    
    # Log authentication attempts for debugging
    if [ "$http_code" = "200" ]; then
        if [ "$body" = "Ok." ]; then
            log_info "Authentication successful for user: $user (password configured)"
            return 0
        else
            log_warning "Authentication returned 200 for user: $user (may indicate no password is set)"
            return 0
        fi
    else
        log_info "Authentication failed for user: $user (HTTP $http_code)"
        return 1
    fi
}

update_qbittorrent_credentials() {
    local current_user="$1"
    local current_pass="$2"
    local new_user="$3"
    local new_pass="$4"

    log_info "Updating qBittorrent credentials to match .env..."

    # First, login with current credentials to get session cookie
    local cookie
    cookie=$(curl -s -i -X POST "http://localhost:8080/api/v2/auth/login" \
        --data-urlencode "username=$current_user" \
        --data-urlencode "password=$current_pass" | \
        grep -i "set-cookie:" | sed -E 's/.*SID=([^;]+).*/SID=\1/')

    if [ -z "$cookie" ]; then
        log_error "Failed to authenticate with qBittorrent"
        return 1
    fi

    # Disable authentication bypass (must be off to set credentials)
    curl -s -X POST "http://localhost:8080/api/v2/app/setPreferences" \
        -H "Cookie: $cookie" \
        --data-urlencode "json={\"web_ui_upnp\":false,\"bypass_local_auth\":false,\"bypass_auth_subnet_whitelist_enabled\":false}" >/dev/null

    # Update preferences with new credentials
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8080/api/v2/app/setPreferences" \
        -H "Cookie: $cookie" \
        --data-urlencode "json={\"web_ui_username\":\"$new_user\",\"web_ui_password\":\"$new_pass\"}")

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "200" ]; then
        log_success "qBittorrent credentials updated"
        
        # Wait a moment for qBittorrent to save config
        sleep 2
        
        # Verify the new credentials work
        if check_qbittorrent_auth "$new_user" "$new_pass"; then
            log_success "New credentials verified successfully"
            return 0
        else
            log_warning "Credentials may not have persisted - retrying after restart"
            docker restart qbittorrent >/dev/null 2>&1
            sleep 10
            
            # Try again with temporary password if it was regenerated
            local temp_pass
            temp_pass=$(get_qbittorrent_temp_password)
            if [ -n "$temp_pass" ] && check_qbittorrent_auth "admin" "$temp_pass"; then
                log_info "Re-authenticated after restart, applying credentials again"
                update_qbittorrent_credentials "admin" "$temp_pass" "$new_user" "$new_pass"
                return $?
            fi
            return 1
        fi
    else
        log_error "Failed to update qBittorrent credentials (HTTP $http_code)"
        return 1
    fi
}

configure_qbittorrent_auth() {
    log_info "Checking qBittorrent authentication status..."
    
    # Try to authenticate with admin/temporary password first (indicates no password set)
    local temp_pass
    temp_pass=$(get_qbittorrent_temp_password)

    if [ -n "$temp_pass" ]; then
        log_info "Found temporary password in logs: ${temp_pass:0:3}... (indicates password not yet configured)"
        if check_qbittorrent_auth "admin" "$temp_pass"; then
            update_qbittorrent_credentials "admin" "$temp_pass" "$QBIT_USER" "$QBIT_PASS"
            return $?
        fi
    else
        log_info "No temporary password found in logs (password may already be configured)"
    fi

    # Try default admin/adminadmin (fresh install default)
    log_info "Trying default credentials (admin/adminadmin)..."
    if check_qbittorrent_auth "admin" "adminadmin"; then
        log_info "Default credentials worked - setting to .env values"
        update_qbittorrent_credentials "admin" "adminadmin" "$QBIT_USER" "$QBIT_PASS"
        return $?
    fi

    # Finally, check if desired credentials already work (password previously set)
    log_info "Checking if .env credentials are already configured..."
    if check_qbittorrent_auth "$QBIT_USER" "$QBIT_PASS"; then
        log_success "qBittorrent credentials already configured correctly"
        return 0
    fi

    # If we get here, we couldn't authenticate with any known credentials
    log_error "Could not authenticate with qBittorrent using any known credentials"
    log_info "Credentials may have been manually changed. Please verify:"
    log_info "  Expected username: $QBIT_USER"
    log_info "  You can reset by deleting config/qbittorrent and restarting"
    return 1
}

# =============================================================================
# API Key Extraction
# =============================================================================

get_sonarr_api_key() {
    local config_file="$PROJECT_DIR/config/sonarr/config.xml"
    if [ -f "$config_file" ]; then
        grep '<ApiKey>' "$config_file" 2>/dev/null | sed -E 's/.*<ApiKey>([^<]+)<\/ApiKey>.*/\1/' || echo ""
    fi
}

get_radarr_api_key() {
    local config_file="$PROJECT_DIR/config/radarr/config.xml"
    if [ -f "$config_file" ]; then
        grep '<ApiKey>' "$config_file" 2>/dev/null | sed -E 's/.*<ApiKey>([^<]+)<\/ApiKey>.*/\1/' || echo ""
    fi
}

get_prowlarr_api_key() {
    local config_file="$PROJECT_DIR/config/prowlarr/config.xml"
    if [ -f "$config_file" ]; then
        grep '<ApiKey>' "$config_file" 2>/dev/null | sed -E 's/.*<ApiKey>([^<]+)<\/ApiKey>.*/\1/' || echo ""
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
        echo "$response" | sed '$d'
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
        echo "$response" | sed '$d'
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
        echo "$response" | sed '$d'
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
        echo "$response" | sed '$d'
        return 1
    fi
}

configure_bazarr_sonarr() {
    # Check if already configured
    local current_settings
    current_settings=$(curl -s "http://localhost:6767/api/system/settings" \
        -H "X-API-KEY: $BAZARR_API_KEY")

    local use_sonarr
    use_sonarr=$(echo "$current_settings" | jq -r '.general.use_sonarr' 2>/dev/null)

    local sonarr_apikey
    sonarr_apikey=$(echo "$current_settings" | jq -r '.sonarr.apikey' 2>/dev/null)

    if [ "$use_sonarr" = "true" ] && [ "$sonarr_apikey" = "$SONARR_API_KEY" ]; then
        log_success "Bazarr → Sonarr already configured"
        return 0
    fi

    log_info "Configuring Bazarr → Sonarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:6767/api/system/settings" \
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
        log_warning "Failed to configure Bazarr → Sonarr automatically (HTTP $http_code)"
        log_info "Please configure manually: Settings → Sonarr → Add Sonarr server"
        return 0
    fi
}

configure_bazarr_radarr() {
    # Check if already configured
    local current_settings
    current_settings=$(curl -s "http://localhost:6767/api/system/settings" \
        -H "X-API-KEY: $BAZARR_API_KEY")

    local use_radarr
    use_radarr=$(echo "$current_settings" | jq -r '.general.use_radarr' 2>/dev/null)

    local radarr_apikey
    radarr_apikey=$(echo "$current_settings" | jq -r '.radarr.apikey' 2>/dev/null)

    if [ "$use_radarr" = "true" ] && [ "$radarr_apikey" = "$RADARR_API_KEY" ]; then
        log_success "Bazarr → Radarr already configured"
        return 0
    fi

    log_info "Configuring Bazarr → Radarr..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:6767/api/system/settings" \
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
        log_warning "Failed to configure Bazarr → Radarr automatically (HTTP $http_code)"
        log_info "Please configure manually: Settings → Radarr → Add Radarr server"
        return 0
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

    log_section "Configuring qBittorrent Authentication"

    configure_qbittorrent_auth

    log_section "Configuring Prowlarr Applications"

    configure_prowlarr_sonarr
    configure_prowlarr_radarr

    log_section "Configuring Download Clients"

    configure_sonarr_qbittorrent
    configure_radarr_qbittorrent

    log_section "Configuring Bazarr"

    configure_bazarr_sonarr
    configure_bazarr_radarr

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
