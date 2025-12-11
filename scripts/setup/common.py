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
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]

                        if key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")


def load_config():
    """Load configuration from setup.config.json."""
    try:
        with open(CONFIG_FILE, "r") as f:
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
        "NC": "\033[0m",
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
    return {header_name: api_key, "Content-Type": "application/json"}


def wait_for_service(
    url,
    api_key,
    service_name,
    endpoint="/api/v3/system/status",
    header_name="X-Api-Key",
    max_retries=30,
    retry_delay=2,
):
    """Wait for a service to become available with detailed error reporting."""
    log(f"Waiting for {service_name} API...", "INFO")
    headers = get_headers(api_key, header_name)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(f"{url}{endpoint}", headers=headers, timeout=10)
            response.raise_for_status()
            log(f"{service_name} API is ready", "SUCCESS")
            return True
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout after 10s: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {str(e)}"
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP {response.status_code}: {str(e)}"
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"

        if attempt % 5 == 0:
            log(
                f"Still waiting for {service_name} (attempt {attempt}/{max_retries}): {last_error}",
                "WARNING",
            )
        time.sleep(retry_delay)

    log(
        f"{service_name} not reachable after {max_retries} attempts. Last error: {last_error}",
        "ERROR",
    )
    sys.exit(1)


def disable_analytics(url, api_key, service_name, api_version="v3", header_name="X-Api-Key"):
    """Disable analytics for *arr services."""
    log("Checking analytics settings...", "INFO")
    headers = get_headers(api_key, header_name)
    config_url = f"{url}/api/{api_version}/config/host"

    try:
        resp = requests.get(config_url, headers=headers, timeout=10)
        resp.raise_for_status()
        config = resp.json()

        if config.get("analyticsEnabled") is False:
            log("Analytics already disabled", "SUCCESS")
            return

        log("Disabling analytics...", "INFO")
        config["analyticsEnabled"] = False

        resp = requests.put(config_url, headers=headers, json=config, timeout=10)
        resp.raise_for_status()
        log("Analytics disabled", "SUCCESS")

    except requests.exceptions.RequestException as e:
        log(f"Failed to disable analytics: {e}", "ERROR")


def configure_config_endpoint(
    url, api_key, endpoint, target_config, config_name, api_version="v3", header_name="X-Api-Key"
):
    """Generic function to configure a config endpoint (media management, naming, etc.)."""
    log(f"Configuring {config_name}...", "INFO")
    headers = get_headers(api_key, header_name)
    config_url = f"{url}/api/{api_version}/config/{endpoint}"

    if not target_config:
        return

    try:
        resp = requests.get(config_url, headers=headers, timeout=10)
        resp.raise_for_status()
        current_config = resp.json()

        needs_update = False
        for key, value in target_config.items():
            if key in current_config and current_config[key] != value:
                current_config[key] = value
                needs_update = True

        if needs_update:
            resp = requests.put(config_url, headers=headers, json=current_config, timeout=10)
            resp.raise_for_status()
            log(f"{config_name} configuration updated", "SUCCESS")
        else:
            log(f"{config_name} configuration already up to date", "SUCCESS")

    except requests.exceptions.RequestException as e:
        log(f"Failed to configure {config_name}: {e}", "ERROR")


def configure_root_folders(url, api_key, root_folders, api_version="v3", header_name="X-Api-Key"):
    """Configure root folders for *arr services."""
    log("Configuring Root Folders...", "INFO")
    headers = get_headers(api_key, header_name)
    rootfolder_url = f"{url}/api/{api_version}/rootfolder"

    try:
        response = requests.get(rootfolder_url, headers=headers, timeout=10)
        response.raise_for_status()
        existing_folders = response.json()
        existing_paths = {f["path"]: f for f in existing_folders}
    except requests.exceptions.RequestException as e:
        log(f"Failed to get root folders: {e}", "ERROR")
        return

    for folder_config in root_folders:
        path = folder_config.get("path", "")
        if not path:
            log("Root folder configuration missing path", "ERROR")
            continue

        if path in existing_paths:
            log(f"Root folder {path} already exists", "SUCCESS")
            continue

        log(f"Adding root folder: {path}", "INFO")
        payload = {"path": path}

        try:
            response = requests.post(rootfolder_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            log(f"Root folder {path} created", "SUCCESS")
        except requests.exceptions.RequestException as e:
            error_msg = e.response.text if hasattr(e, "response") and e.response else str(e)
            log(f"Failed to create root folder {path}: {error_msg}", "ERROR")


def configure_download_clients(
    url, api_key, download_clients, api_version="v3", header_name="X-Api-Key"
):
    """Configure download clients for *arr services with improved error handling."""
    log("Configuring Download Clients...", "INFO")
    headers = get_headers(api_key, header_name)
    downloadclient_url = f"{url}/api/{api_version}/downloadclient"

    try:
        response = requests.get(downloadclient_url, headers=headers, timeout=10)
        response.raise_for_status()
        existing_clients = response.json()
        existing_map = {c["name"]: c for c in existing_clients}
    except requests.exceptions.RequestException as e:
        log(f"Failed to get download clients: {e}", "ERROR")
        return

    for client_config in download_clients:
        name = client_config.get("name", "Unknown")
        log(f"Processing download client: {name}", "INFO")

        # Validate required fields
        if not all(key in client_config for key in ["protocol", "implementation"]):
            log(f"Download client {name} missing required configuration fields", "ERROR")
            continue

        fields = []
        missing_env_vars = []

        for field in client_config.get("fields", []):
            value = field.get("value")
            if "env" in field:
                env_val = os.environ.get(field["env"])
                if env_val:
                    value = env_val
                else:
                    missing_env_vars.append(field["env"])
                    log(
                        f"Environment variable {field['env']} not found for field {field['name']}",
                        "WARNING",
                    )

            fields.append({"name": field["name"], "value": value})

        if missing_env_vars:
            log(
                f"Download client {name} has missing environment variables: {', '.join(missing_env_vars)}",
                "WARNING",
            )

        payload = {
            "enable": True,
            "protocol": client_config["protocol"],
            "priority": client_config.get("priority", 1),
            "name": name,
            "implementation": client_config["implementation"],
            "implementationName": client_config["implementation"],
            "configContract": f"{client_config['implementation']}Settings",
            "fields": fields,
        }

        if name in existing_map:
            payload["id"] = existing_map[name]["id"]
            try:
                response = requests.put(
                    f"{downloadclient_url}/{payload['id']}",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                response.raise_for_status()
                log(f"Download client {name} updated", "SUCCESS")
            except requests.exceptions.RequestException as e:
                error_msg = e.response.text if hasattr(e, "response") and e.response else str(e)
                log(f"Failed to update {name}: {error_msg}", "ERROR")
        else:
            try:
                response = requests.post(
                    downloadclient_url, headers=headers, json=payload, timeout=10
                )
                response.raise_for_status()
                log(f"Download client {name} created", "SUCCESS")
            except requests.exceptions.RequestException as e:
                error_msg = e.response.text if hasattr(e, "response") and e.response else str(e)
                log(f"Failed to create {name}: {error_msg}", "ERROR")
