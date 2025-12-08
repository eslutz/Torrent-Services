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
PROWLARR_CONFIG = CONFIG.get("prowlarr", {})
PROWLARR_URL = PROWLARR_CONFIG.get("url", "http://localhost:9696")

def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m"
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")

def get_api_key():
    api_key = os.environ.get("PROWLARR_API_KEY")
    if not api_key:
        log("PROWLARR_API_KEY not set in environment", "ERROR")
        sys.exit(1)
    log(f"Using API Key: {api_key[:5]}...", "INFO")
    return api_key

def get_headers(api_key):
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

def wait_for_prowlarr(api_key):
    log("Waiting for Prowlarr API...", "INFO")
    for _ in range(30):
        try:
            requests.get(f"{PROWLARR_URL}/api/v1/system/status", headers=get_headers(api_key))
            return
        except:
            time.sleep(2)
    log("Prowlarr not reachable", "ERROR")
    sys.exit(1)

def get_tag_id(label, api_key):
    headers = get_headers(api_key)
    tags = requests.get(f"{PROWLARR_URL}/api/v1/tag", headers=headers).json()
    for tag in tags:
        if tag["label"] == label:
            return tag["id"]
    
    # Create tag
    log(f"Creating tag: {label}", "INFO")
    resp = requests.post(f"{PROWLARR_URL}/api/v1/tag", headers=headers, json={"label": label})
    resp.raise_for_status()
    return resp.json()["id"]

def configure_proxy(api_key):
    log("Configuring Tor Proxy...", "INFO")
    headers = get_headers(api_key)
    
    # Get tag ID
    tag_id = get_tag_id("tor-proxy", api_key)
    
    # Check existing proxies
    proxies = requests.get(f"{PROWLARR_URL}/api/v1/indexerproxy", headers=headers).json()
    existing = next((p for p in proxies if p["name"] == "Tor"), None)
    
    payload = {
        "name": "Tor",
        "implementationName": "Socks5",
        "implementation": "Socks5",
        "configContract": "Socks5Settings",
        "fields": [
            {"name": "host", "value": "torarr"},
            {"name": "port", "value": 9050},
            {"name": "username", "value": ""},
            {"name": "password", "value": ""}
        ],
        "tags": [tag_id]
    }
    
    if existing:
        payload["id"] = existing["id"]
        requests.put(f"{PROWLARR_URL}/api/v1/indexerproxy/{existing['id']}", headers=headers, json=payload).raise_for_status()
        log("Tor Proxy updated", "SUCCESS")
    else:
        requests.post(f"{PROWLARR_URL}/api/v1/indexerproxy", headers=headers, json=payload).raise_for_status()
        log("Tor Proxy created", "SUCCESS")

def get_schema_for_indexer(name, api_key):
    headers = get_headers(api_key)
    schemas = requests.get(f"{PROWLARR_URL}/api/v1/indexer/schema", headers=headers).json()
    return next((s for s in schemas if s["name"] == name), None)

def configure_indexers(api_key):
    log("Configuring Indexers...", "INFO")
    headers = get_headers(api_key)
    
    # Get existing indexers
    existing_indexers = requests.get(f"{PROWLARR_URL}/api/v1/indexer", headers=headers).json()
    existing_map = {i["name"]: i for i in existing_indexers}
    
    for idx_config in PROWLARR_CONFIG.get("indexers", []):
        name = idx_config["name"]
        log(f"Processing indexer: {name}", "INFO")
        
        schema = get_schema_for_indexer(name, api_key)
        if not schema:
            log(f"Schema not found for {name}, skipping", "WARNING")
            continue
            
        # Prepare fields
        if name in existing_map:
            fields = existing_map[name]["fields"]
        else:
            fields = schema["fields"]
        
        # Apply overrides from config
        if "fields" in idx_config:
            for override in idx_config["fields"]:
                for field in fields:
                    if field["name"] == override["name"]:
                        field["value"] = override["value"]
        
        # Apply secrets from env
        if "secrets" in idx_config:
            for secret in idx_config["secrets"]:
                env_val = os.environ.get(secret["env"])
                if env_val:
                    for field in fields:
                        if field["name"] == secret["field"]:
                            field["value"] = env_val
                else:
                    log(f"Secret env var {secret['env']} not found for {name}", "WARNING")

        # Prepare tags
        tag_ids = []
        if "tags" in idx_config:
            for tag_label in idx_config["tags"]:
                tag_ids.append(get_tag_id(tag_label, api_key))
        
        payload = {
            "name": name,
            "implementation": schema["implementation"],
            "implementationName": schema["implementationName"],
            "configContract": schema["configContract"],
            "fields": fields,
            "enable": True,
            "protocol": schema["protocol"],
            "priority": idx_config.get("priority", 25),
            "tags": tag_ids,
            "appProfileId": 1
        }
        
        if name in existing_map:
            payload["id"] = existing_map[name]["id"]
            # Preserve existing fields if not overridden? No, full sync based on config is better for "setup" script.
            try:
                requests.put(f"{PROWLARR_URL}/api/v1/indexer/{payload['id']}", headers=headers, json=payload).raise_for_status()
                log(f"Indexer {name} updated", "SUCCESS")
            except Exception as e:
                error_msg = e.response.text if hasattr(e, 'response') and e.response else str(e)
                log(f"Failed to update {name}: {error_msg}", "ERROR")
        else:
            try:
                requests.post(f"{PROWLARR_URL}/api/v1/indexer", headers=headers, json=payload).raise_for_status()
                log(f"Indexer {name} created", "SUCCESS")
            except Exception as e:
                error_msg = e.response.text if hasattr(e, 'response') and e.response else str(e)
                log(f"Failed to create {name}: {error_msg}", "ERROR")

def configure_apps(api_key):
    log("Configuring Applications...", "INFO")
    headers = get_headers(api_key)
    
    sonarr_key = os.environ.get("SONARR_API_KEY")
    radarr_key = os.environ.get("RADARR_API_KEY")
    
    apps = requests.get(f"{PROWLARR_URL}/api/v1/applications", headers=headers).json()
    app_map = {a["name"]: a for a in apps}
    
    # Sonarr
    if sonarr_key:
        payload = {
            "name": "Sonarr",
            "syncLevel": "fullSync",
            "implementation": "Sonarr",
            "configContract": "SonarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://sonarr:8989"},
                {"name": "apiKey", "value": sonarr_key},
                {"name": "syncCategories", "value": [5000, 5010, 5020, 5030, 5040, 5045, 5050]}
            ],
            "tags": []
        }
        if "Sonarr" in app_map:
            payload["id"] = app_map["Sonarr"]["id"]
            requests.put(f"{PROWLARR_URL}/api/v1/applications/{payload['id']}", headers=headers, json=payload)
            log("Sonarr app updated", "SUCCESS")
        else:
            requests.post(f"{PROWLARR_URL}/api/v1/applications", headers=headers, json=payload)
            log("Sonarr app created", "SUCCESS")
            
    # Radarr
    if radarr_key:
        payload = {
            "name": "Radarr",
            "syncLevel": "fullSync",
            "implementation": "Radarr",
            "configContract": "RadarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://radarr:7878"},
                {"name": "apiKey", "value": radarr_key},
                {"name": "syncCategories", "value": [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060]}
            ],
            "tags": []
        }
        if "Radarr" in app_map:
            payload["id"] = app_map["Radarr"]["id"]
            requests.put(f"{PROWLARR_URL}/api/v1/applications/{payload['id']}", headers=headers, json=payload)
            log("Radarr app updated", "SUCCESS")
        else:
            requests.post(f"{PROWLARR_URL}/api/v1/applications", headers=headers, json=payload)
            log("Radarr app created", "SUCCESS")

def disable_analytics(api_key):
    log("Checking analytics settings...", "INFO")
    headers = get_headers(api_key)
    
    try:
        # Get current config
        resp = requests.get(f"{PROWLARR_URL}/api/v1/config/host", headers=headers)
        resp.raise_for_status()
        config = resp.json()
        
        if config.get("analyticsEnabled") is False:
            log("Analytics already disabled", "SUCCESS")
            return

        log("Disabling analytics...", "INFO")
        config["analyticsEnabled"] = False
        
        # Update config
        requests.put(f"{PROWLARR_URL}/api/v1/config/host", headers=headers, json=config).raise_for_status()
        log("Analytics disabled", "SUCCESS")
        
        # Restart to apply? Usually not strictly required for analytics but good practice if changed
        # However, restarting via API might kill the script connection if not careful.
        # Prowlarr applies this setting immediately without restart usually.
        
    except Exception as e:
        log(f"Failed to disable analytics: {e}", "ERROR")

def main():
    api_key = get_api_key()
    wait_for_prowlarr(api_key)
    disable_analytics(api_key)
    configure_proxy(api_key)
    configure_indexers(api_key)
    configure_apps(api_key)

if __name__ == "__main__":
    main()
