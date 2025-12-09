import os
import requests
from common import load_env, load_config, log, get_api_key, get_headers

load_env()

CONFIG = load_config()
BAZARR_CONFIG = CONFIG.get("bazarr", {})
BAZARR_URL = os.environ.get("BAZARR_URL", BAZARR_CONFIG.get("url", "http://localhost:6767"))

def wait_for_bazarr(api_key):
    log("Waiting for Bazarr API...", "INFO")
    headers = get_headers(api_key, "X-API-KEY")
    import time
    for _ in range(30):
        try:
            requests.get(f"{BAZARR_URL}/api/system/status", headers=headers)
            log("Bazarr API is ready", "SUCCESS")
            return
        except:
            time.sleep(2)
    log("Bazarr not reachable", "ERROR")
    import sys
    sys.exit(1)

def configure_sonarr(bazarr_api_key, sonarr_api_key):
    log("Configuring Bazarr -> Sonarr...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")
    
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
        import sys
        log(f"Failed to configure Bazarr -> Sonarr: {e}", "ERROR")
        sys.exit(1)

def configure_radarr(bazarr_api_key, radarr_api_key):
    log("Configuring Bazarr -> Radarr...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")
    
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
        import sys
        log(f"Failed to configure Bazarr -> Radarr: {e}", "ERROR")
        sys.exit(1)

def configure_general_settings(bazarr_api_key):
    log("Configuring Bazarr general settings...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")
    general_config = BAZARR_CONFIG.get("general", {})
    
    if not general_config:
        return
    
    payload = {"general": {}}
    
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

def disable_analytics(api_key):
    log("Checking analytics settings...", "INFO")
    headers = get_headers(api_key, "X-API-KEY")
    
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
    
    bazarr_api_key = get_api_key("BAZARR_API_KEY")
    sonarr_api_key = get_api_key("SONARR_API_KEY")
    radarr_api_key = get_api_key("RADARR_API_KEY")
    
    wait_for_bazarr(bazarr_api_key)
    disable_analytics(bazarr_api_key)
    
    configure_sonarr(bazarr_api_key, sonarr_api_key)
    configure_radarr(bazarr_api_key, radarr_api_key)
    configure_general_settings(bazarr_api_key)
    
    log("Bazarr setup completed successfully", "SUCCESS")

if __name__ == "__main__":
    main()
