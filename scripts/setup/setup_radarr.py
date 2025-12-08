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
RADARR_URL = CONFIG.get("radarr", {}).get("url", "http://localhost:7878")

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
    api_key = os.environ.get("RADARR_API_KEY")
    if not api_key:
        log("RADARR_API_KEY not set in environment", "ERROR")
        sys.exit(1)
    log(f"Using API Key: {api_key[:5]}...", "INFO")
    return api_key

def get_headers(api_key):
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

def wait_for_radarr(api_key):
    log("Waiting for Radarr API...", "INFO")
    for _ in range(30):
        try:
            requests.get(f"{RADARR_URL}/api/v3/system/status", headers=get_headers(api_key))
            return
        except:
            time.sleep(2)
    log("Radarr not reachable", "ERROR")
    sys.exit(1)

def configure_analytics(api_key):
    log("Configuring Analytics...", "INFO")
    headers = get_headers(api_key)
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/config/host", headers=headers)
        resp.raise_for_status()
        config = resp.json()
        
        if config.get("analyticsEnabled") is True:
            config["analyticsEnabled"] = False
            requests.put(f"{RADARR_URL}/api/v3/config/host", headers=headers, json=config).raise_for_status()
            log("Analytics disabled", "SUCCESS")
        else:
            log("Analytics already disabled", "INFO")
    except Exception as e:
        log(f"Failed to configure analytics: {e}", "ERROR")

def configure_media_management(api_key):
    log("Configuring Media Management...", "INFO")
    headers = get_headers(api_key)
    target_config = CONFIG.get("radarr", {}).get("media_management", {})
    
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/config/mediaManagement", headers=headers)
        resp.raise_for_status()
        current_config = resp.json()
        
        needs_update = False
        for key, value in target_config.items():
            if key in current_config and current_config[key] != value:
                current_config[key] = value
                needs_update = True
        
        if needs_update:
            requests.put(f"{RADARR_URL}/api/v3/config/mediaManagement", headers=headers, json=current_config).raise_for_status()
            log("Media Management updated", "SUCCESS")
        else:
            log("Media Management already up to date", "INFO")
    except Exception as e:
        log(f"Failed to configure media management: {e}", "ERROR")

def configure_naming(api_key):
    log("Configuring Naming...", "INFO")
    headers = get_headers(api_key)
    target_config = CONFIG.get("radarr", {}).get("naming", {})
    
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/config/naming", headers=headers)
        resp.raise_for_status()
        current_config = resp.json()
        
        needs_update = False
        for key, value in target_config.items():
            if key in current_config and current_config[key] != value:
                current_config[key] = value
                needs_update = True
        
        if needs_update:
            requests.put(f"{RADARR_URL}/api/v3/config/naming", headers=headers, json=current_config).raise_for_status()
            log("Naming configuration updated", "SUCCESS")
        else:
            log("Naming configuration already up to date", "INFO")
    except Exception as e:
        log(f"Failed to configure naming: {e}", "ERROR")

def configure_root_folders(api_key):
    log("Configuring Root Folders...", "INFO")
    headers = get_headers(api_key)
    root_folders = CONFIG.get("radarr", {}).get("root_folders", [])
    
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/rootfolder", headers=headers)
        resp.raise_for_status()
        existing_folders = resp.json()
        existing_paths = [f["path"] for f in existing_folders]
        
        for folder in root_folders:
            path = folder["path"]
            if path not in existing_paths:
                payload = {"path": path}
                requests.post(f"{RADARR_URL}/api/v3/rootfolder", headers=headers, json=payload).raise_for_status()
                log(f"Root folder added: {path}", "SUCCESS")
            else:
                log(f"Root folder exists: {path}", "INFO")
    except Exception as e:
        log(f"Failed to configure root folders: {e}", "ERROR")

def get_schema_for_client(implementation, api_key):
    headers = get_headers(api_key)
    schemas = requests.get(f"{RADARR_URL}/api/v3/downloadclient/schema", headers=headers).json()
    return next((s for s in schemas if s["implementation"] == implementation), None)

def configure_download_clients(api_key):
    log("Configuring Download Clients...", "INFO")
    headers = get_headers(api_key)
    clients = CONFIG.get("radarr", {}).get("download_clients", [])
    
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/downloadclient", headers=headers)
        resp.raise_for_status()
        existing_clients = resp.json()
        existing_map = {c["name"]: c for c in existing_clients}
        
        for client_config in clients:
            name = client_config["name"]
            implementation = client_config["implementation"]
            
            schema = get_schema_for_client(implementation, api_key)
            if not schema:
                log(f"Schema not found for {implementation}, skipping", "WARNING")
                continue
            
            # Prepare fields
            if name in existing_map:
                fields = existing_map[name]["fields"]
            else:
                fields = schema["fields"]
            
            # Apply overrides from config
            if "fields" in client_config:
                for override in client_config["fields"]:
                    # Handle env var substitution
                    value = override.get("value")
                    if "env" in override:
                        env_val = os.environ.get(override["env"])
                        if env_val:
                            value = env_val
                        else:
                            log(f"Environment variable {override['env']} not found for {name}", "WARNING")
                    
                    # Update field
                    found = False
                    for field in fields:
                        if field["name"] == override["name"]:
                            field["value"] = value
                            found = True
                            break
                    if not found:
                        # If field not in schema/existing, add it (though usually schema dictates fields)
                        pass

            payload = {
                "name": name,
                "implementation": implementation,
                "protocol": client_config["protocol"],
                "configContract": schema["configContract"],
                "fields": fields,
                "enable": True,
                "priority": 1
            }
            
            if name in existing_map:
                payload["id"] = existing_map[name]["id"]
                requests.put(f"{RADARR_URL}/api/v3/downloadclient/{payload['id']}", headers=headers, json=payload).raise_for_status()
                log(f"Download client {name} updated", "SUCCESS")
            else:
                requests.post(f"{RADARR_URL}/api/v3/downloadclient", headers=headers, json=payload).raise_for_status()
                log(f"Download client {name} created", "SUCCESS")
                
    except Exception as e:
        log(f"Failed to configure download clients: {e}", "ERROR")

def main():
    log("Starting Radarr Setup...", "INFO")
    api_key = get_api_key()
    wait_for_radarr(api_key)
    
    configure_analytics(api_key)
    configure_media_management(api_key)
    configure_naming(api_key)
    configure_root_folders(api_key)
    configure_download_clients(api_key)
    
    log("Radarr Setup Complete!", "SUCCESS")

if __name__ == "__main__":
    main()
