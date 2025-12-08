import os
import json
import requests
import sys
import time

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "setup.config.json")

def load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, "../../"))
    env_path = os.path.join(root_dir, ".env")
    
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")

load_env()

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load config file: {e}")
        sys.exit(1)

CONFIG = load_config()
BAZARR_CONFIG = CONFIG.get("bazarr", {})
BAZARR_URL = BAZARR_CONFIG.get("url", "http://localhost:6767")

def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m"
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")

def get_api_key(service_name, env_var):
    api_key = os.environ.get(env_var)
    if not api_key:
        log(f"{env_var} not set in environment", "ERROR")
        sys.exit(1)
    return api_key

def get_headers(api_key):
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

def wait_for_bazarr(api_key):
    log("Waiting for Bazarr API...", "INFO")
    for _ in range(30):
        try:
            requests.get(f"{BAZARR_URL}/api/system/status", headers=get_headers(api_key))
            return
        except:
            time.sleep(2)
    log("Bazarr not reachable", "ERROR")
    sys.exit(1)

def configure_sonarr(bazarr_api_key, sonarr_api_key):
    log("Configuring Bazarr -> Sonarr...", "INFO")
    headers = get_headers(bazarr_api_key)
    
    # Check if already configured
    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/settings", headers=headers)
        resp.raise_for_status()
        current_settings = resp.json()
        
        use_sonarr = current_settings.get("general", {}).get("use_sonarr", False)
        current_sonarr_apikey = current_settings.get("sonarr", {}).get("apikey", "")
        
        if use_sonarr and current_sonarr_apikey == sonarr_api_key:
            log("Bazarr -> Sonarr already configured", "SUCCESS")
            return
    except Exception as e:
        log(f"Failed to check current settings: {e}", "WARNING")

    payload = {
        "sonarr": {
            "ip": "sonarr",
            "port": 8989,
            "base_url": "",
            "ssl": False,
            "apikey": sonarr_api_key,
            "full_update": "Daily",
            "full_update_day": 6,
            "full_update_hour": 4,
            "only_monitored": True,
            "series_sync": 60,
            "excluded_tags": [],
            "excluded_series_types": []
        },
        "general": {
            "use_sonarr": True
        }
    }
    
    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr -> Sonarr configured", "SUCCESS")
    except Exception as e:
        log(f"Failed to configure Bazarr -> Sonarr: {e}", "ERROR")
        sys.exit(1)

def configure_radarr(bazarr_api_key, radarr_api_key):
    log("Configuring Bazarr -> Radarr...", "INFO")
    headers = get_headers(bazarr_api_key)
    
    # Check if already configured
    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/settings", headers=headers)
        resp.raise_for_status()
        current_settings = resp.json()
        
        use_radarr = current_settings.get("general", {}).get("use_radarr", False)
        current_radarr_apikey = current_settings.get("radarr", {}).get("apikey", "")
        
        if use_radarr and current_radarr_apikey == radarr_api_key:
            log("Bazarr -> Radarr already configured", "SUCCESS")
            return
    except Exception as e:
        log(f"Failed to check current settings: {e}", "WARNING")

    payload = {
        "radarr": {
            "ip": "radarr",
            "port": 7878,
            "base_url": "",
            "ssl": False,
            "apikey": radarr_api_key,
            "full_update": "Daily",
            "full_update_day": 6,
            "full_update_hour": 4,
            "only_monitored": True,
            "movies_sync": 60,
            "excluded_tags": []
        },
        "general": {
            "use_radarr": True
        }
    }
    
    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr -> Radarr configured", "SUCCESS")
    except Exception as e:
        log(f"Failed to configure Bazarr -> Radarr: {e}", "ERROR")
        sys.exit(1)

def configure_general_settings(bazarr_api_key):
    log("Configuring Bazarr general settings...", "INFO")
    headers = get_headers(bazarr_api_key)
    general_config = BAZARR_CONFIG.get("general", {})
    
    if not general_config:
        return

    # Map config keys to Bazarr settings keys if they differ
    # Based on setup.config.json:
    # "enabled_providers": ["addic7ed", "podnapisi", "opensubtitlescom"],
    # "adaptive_searching": true,
    # "minimum_score": 80,
    # "minimum_score_movie": 80,
    # "days_to_upgrade_subs": 7
    
    # We need to fetch current settings first to merge, as POST /api/system/settings might require full objects or specific structure
    # Actually, Bazarr API documentation says "Update Bazarr settings. You can update only one section or multiple sections."
    # So we can just send the "general" section.
    
    payload = {
        "general": {}
    }
    
    if "enabled_providers" in general_config:
        payload["general"]["enabled_providers"] = general_config["enabled_providers"]
    if "adaptive_searching" in general_config:
        payload["general"]["adaptive_searching"] = general_config["adaptive_searching"]
    if "minimum_score" in general_config:
        payload["general"]["minimum_score"] = general_config["minimum_score"]
    if "minimum_score_movie" in general_config:
        payload["general"]["minimum_score_movie"] = general_config["minimum_score_movie"]
    if "days_to_upgrade_subs" in general_config:
        payload["general"]["days_to_upgrade_subs"] = general_config["days_to_upgrade_subs"]
        
    if not payload["general"]:
        return

    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr general settings configured", "SUCCESS")
    except Exception as e:
        log(f"Failed to configure Bazarr general settings: {e}", "ERROR")
        # Don't exit here, as this is optional configuration

def disable_analytics(api_key):
    log("Checking analytics settings...", "INFO")
    headers = get_headers(api_key)
    
    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/settings", headers=headers)
        resp.raise_for_status()
        settings = resp.json()
        
        if settings.get("general", {}).get("analytics_enabled") is False:
            log("Analytics already disabled", "SUCCESS")
            return

        log("Disabling analytics...", "INFO")
        
        payload = {
            "general": {
                "analytics_enabled": False
            }
        }
        
        requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload).raise_for_status()
        log("Analytics disabled", "SUCCESS")
        
    except Exception as e:
        log(f"Failed to disable analytics: {e}", "ERROR")

def main():
    log("Starting Bazarr setup...", "INFO")
    
    bazarr_api_key = get_api_key("Bazarr", "BAZARR_API_KEY")
    sonarr_api_key = get_api_key("Sonarr", "SONARR_API_KEY")
    radarr_api_key = get_api_key("Radarr", "RADARR_API_KEY")
    
    wait_for_bazarr(bazarr_api_key)
    disable_analytics(bazarr_api_key)
    
    configure_sonarr(bazarr_api_key, sonarr_api_key)
    configure_radarr(bazarr_api_key, radarr_api_key)
    configure_general_settings(bazarr_api_key)
    
    log("Bazarr setup completed successfully", "SUCCESS")

if __name__ == "__main__":
    main()
