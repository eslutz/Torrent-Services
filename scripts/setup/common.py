import os
import json
import requests
import sys
import time

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "setup.config.json")

def load_env():
    """Load environment variables from .env file in the repository root."""
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

def load_config():
    """Load configuration from setup.config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load config file: {e}")
        sys.exit(1)

def log(msg, level="INFO"):
    """Print colored log messages."""
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m"
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")

def get_api_key(env_var):
    """Get API key from environment variable."""
    api_key = os.environ.get(env_var)
    if not api_key:
        log(f"{env_var} not set in environment", "ERROR")
        sys.exit(1)
    return api_key

def get_headers(api_key, header_name="X-Api-Key"):
    """Get standard headers for API requests."""
    return {
        header_name: api_key,
        "Content-Type": "application/json"
    }

def wait_for_service(url, api_key, service_name, endpoint="/api/v3/system/status", header_name="X-Api-Key", max_retries=30, retry_delay=2):
    """Wait for a service to become available."""
    log(f"Waiting for {service_name} API...", "INFO")
    headers = get_headers(api_key, header_name)
    
    for _ in range(max_retries):
        try:
            response = requests.get(f"{url}{endpoint}", headers=headers)
            response.raise_for_status()
            log(f"{service_name} API is ready", "SUCCESS")
            return True
        except:
            time.sleep(retry_delay)
    
    log(f"{service_name} not reachable", "ERROR")
    sys.exit(1)

def disable_analytics(url, api_key, service_name, api_version="v3", header_name="X-Api-Key"):
    """Disable analytics for *arr services."""
    log("Checking analytics settings...", "INFO")
    headers = get_headers(api_key, header_name)
    config_url = f"{url}/api/{api_version}/config/host"
    
    try:
        resp = requests.get(config_url, headers=headers)
        resp.raise_for_status()
        config = resp.json()
        
        if config.get("analyticsEnabled") is False:
            log("Analytics already disabled", "SUCCESS")
            return
        
        log("Disabling analytics...", "INFO")
        config["analyticsEnabled"] = False
        
        requests.put(config_url, headers=headers, json=config).raise_for_status()
        log("Analytics disabled", "SUCCESS")
        
    except Exception as e:
        log(f"Failed to disable analytics: {e}", "ERROR")

def configure_config_endpoint(url, api_key, endpoint, target_config, config_name, api_version="v3", header_name="X-Api-Key"):
    """Generic function to configure a config endpoint (media management, naming, etc.)."""
    log(f"Configuring {config_name}...", "INFO")
    headers = get_headers(api_key, header_name)
    config_url = f"{url}/api/{api_version}/config/{endpoint}"
    
    if not target_config:
        return
    
    try:
        resp = requests.get(config_url, headers=headers)
        resp.raise_for_status()
        current_config = resp.json()
        
        needs_update = False
        for key, value in target_config.items():
            if key in current_config and current_config[key] != value:
                current_config[key] = value
                needs_update = True
        
        if needs_update:
            requests.put(config_url, headers=headers, json=current_config).raise_for_status()
            log(f"{config_name} configuration updated", "SUCCESS")
        else:
            log(f"{config_name} configuration already up to date", "SUCCESS")
            
    except Exception as e:
        log(f"Failed to configure {config_name}: {e}", "ERROR")

def configure_root_folders(url, api_key, root_folders, api_version="v3", header_name="X-Api-Key"):
    """Configure root folders for *arr services."""
    log("Configuring Root Folders...", "INFO")
    headers = get_headers(api_key, header_name)
    rootfolder_url = f"{url}/api/{api_version}/rootfolder"
    
    try:
        existing_folders = requests.get(rootfolder_url, headers=headers).json()
        existing_paths = {f["path"]: f for f in existing_folders}
    except Exception as e:
        log(f"Failed to get root folders: {e}", "ERROR")
        return
    
    for folder_config in root_folders:
        path = folder_config["path"]
        if path in existing_paths:
            log(f"Root folder {path} already exists", "SUCCESS")
            continue
            
        log(f"Adding root folder: {path}", "INFO")
        payload = {"path": path}
        
        try:
            requests.post(rootfolder_url, headers=headers, json=payload).raise_for_status()
            log(f"Root folder {path} created", "SUCCESS")
        except Exception as e:
            error_msg = e.response.text if hasattr(e, 'response') and e.response else str(e)
            log(f"Failed to create root folder {path}: {error_msg}", "ERROR")

def configure_download_clients(url, api_key, download_clients, api_version="v3", header_name="X-Api-Key"):
    """Configure download clients for *arr services."""
    log("Configuring Download Clients...", "INFO")
    headers = get_headers(api_key, header_name)
    downloadclient_url = f"{url}/api/{api_version}/downloadclient"
    
    try:
        existing_clients = requests.get(downloadclient_url, headers=headers).json()
        existing_map = {c["name"]: c for c in existing_clients}
    except Exception as e:
        log(f"Failed to get download clients: {e}", "ERROR")
        return
    
    for client_config in download_clients:
        name = client_config["name"]
        log(f"Processing download client: {name}", "INFO")
        
        fields = []
        for field in client_config.get("fields", []):
            value = field.get("value")
            if "env" in field:
                env_val = os.environ.get(field["env"])
                if env_val:
                    value = env_val
                else:
                    log(f"Environment variable {field['env']} not found for field {field['name']}", "WARNING")
            
            fields.append({
                "name": field["name"],
                "value": value
            })
        
        payload = {
            "enable": True,
            "protocol": client_config["protocol"],
            "priority": client_config.get("priority", 1),
            "name": name,
            "implementation": client_config["implementation"],
            "implementationName": client_config["implementation"],
            "configContract": f"{client_config['implementation']}Settings",
            "fields": fields
        }
        
        if name in existing_map:
            payload["id"] = existing_map[name]["id"]
            try:
                requests.put(f"{downloadclient_url}/{payload['id']}", headers=headers, json=payload).raise_for_status()
                log(f"Download client {name} updated", "SUCCESS")
            except Exception as e:
                log(f"Failed to update {name}: {e}", "ERROR")
        else:
            try:
                requests.post(downloadclient_url, headers=headers, json=payload).raise_for_status()
                log(f"Download client {name} created", "SUCCESS")
            except Exception as e:
                log(f"Failed to create {name}: {e}", "ERROR")
