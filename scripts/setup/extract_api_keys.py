import os
import re
import xml.etree.ElementTree as ET
import sys


def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m",
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")


# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
ENV_FILE = os.path.join(PROJECT_DIR, ".env")


def get_config_path(service, filename):
    return os.path.join(PROJECT_DIR, "config", service, filename)


def extract_xml_key(filepath):
    if not os.path.exists(filepath):
        log(f"Config file not found at {filepath}", "WARNING")
        return None
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        # Sonarr/Radarr/Prowlarr config.xml usually has <ApiKey>
        api_key = root.find("ApiKey")
        if api_key is not None:
            return api_key.text
    except Exception as e:
        log(f"Error parsing {filepath}: {e}", "ERROR")
    return None


def extract_bazarr_key(filepath):
    # Bazarr uses config.yaml
    if not os.path.exists(filepath):
        log(f"Config file not found at {filepath}", "WARNING")
        return None
    try:
        with open(filepath, "r") as f:
            content = f.read()
            # Look for 'apikey: value' - API keys can contain alphanumeric, underscores, and hyphens
            match = re.search(r'^\s*apikey:\s*[\'"]?([a-zA-Z0-9_-]+)[\'"]?', content, re.MULTILINE)
            if match:
                return match.group(1)
    except Exception as e:
        log(f"Error reading {filepath}: {e}", "ERROR")
    return None


def update_env_file(keys):
    if not os.path.exists(ENV_FILE):
        log(f".env file not found at {ENV_FILE}", "ERROR")
        return False

    with open(ENV_FILE, "r") as f:
        lines = f.readlines()

    new_lines = []
    processed_keys = set()

    for line in lines:
        # Check if line matches a key we want to update
        updated = False
        for key, value in keys.items():
            if value and line.strip().startswith(f"{key}="):
                new_lines.append(f'{key}="{value}"\n')
                processed_keys.add(key)
                updated = True
                log(f"Updated {key} in .env", "SUCCESS")
                break
        if not updated:
            new_lines.append(line)

    # Append new keys if they weren't found
    for key, value in keys.items():
        if value and key not in processed_keys:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f'{key}="{value}"\n')
            log(f"Added {key} to .env", "SUCCESS")

    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)
    return True


def main():
    log("Extracting API Keys...", "INFO")

    # Sonarr
    sonarr_key = extract_xml_key(get_config_path("sonarr", "config.xml"))
    if sonarr_key:
        log(f"Found Sonarr API Key: {sonarr_key[:5]}...", "INFO")
        update_env_file({"SONARR_API_KEY": sonarr_key})

    # Radarr
    radarr_key = extract_xml_key(get_config_path("radarr", "config.xml"))
    if radarr_key:
        log(f"Found Radarr API Key: {radarr_key[:5]}...", "INFO")
        update_env_file({"RADARR_API_KEY": radarr_key})

    # Prowlarr
    prowlarr_key = extract_xml_key(get_config_path("prowlarr", "config.xml"))
    if prowlarr_key:
        log(f"Found Prowlarr API Key: {prowlarr_key[:5]}...", "INFO")
        update_env_file({"PROWLARR_API_KEY": prowlarr_key})

    # Bazarr
    # Bazarr config is nested deeper: config/bazarr/config/config.yaml
    bazarr_key = extract_bazarr_key(os.path.join(PROJECT_DIR, "config/bazarr/config/config.yaml"))
    if bazarr_key:
        log(f"Found Bazarr API Key: {bazarr_key[:5]}...", "INFO")
        update_env_file({"BAZARR_API_KEY": bazarr_key})

    log("API Key extraction complete", "SUCCESS")


if __name__ == "__main__":
    main()
