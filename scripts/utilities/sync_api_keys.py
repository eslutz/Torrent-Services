#!/usr/bin/env python3
"""
Sync and validate API keys between services.

This script:
1. Validates and syncs Prowlarr API keys to Sonarr/Radarr indexers
2. Extracts Notifiarr API key from config/logs if missing from .env
3. Updates .env file with discovered keys
"""

import os
import re
import sys
import json
import subprocess
import requests
from pathlib import Path


def log(msg, level="INFO"):
    """Print colored log messages."""
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
    }
    end = "\033[0m"
    print(f"{colors.get(level, '')}[{level}] {msg}{end}")


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


def update_env_file(key_name, api_key):
    """Update .env file with an API key."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, "../../"))
    env_path = Path(root_dir) / ".env"

    if not env_path.exists():
        log(".env file not found", "ERROR")
        return False

    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        # Check if key already exists
        key_exists = False
        updated_lines = []

        for line in lines:
            if line.strip().startswith(f"{key_name}="):
                key_exists = True
                # Update the existing line
                updated_lines.append(f'{key_name}="{api_key}"\n')
                log(f"Updated existing {key_name} in .env", "SUCCESS")
            else:
                updated_lines.append(line)

        if not key_exists:
            # Add the key at the end, checking for trailing newline
            if updated_lines and not updated_lines[-1].endswith('\n'):
                updated_lines.append('\n')
            updated_lines.append(f'{key_name}="{api_key}"\n')
            log(f"Added {key_name} to .env", "SUCCESS")

        # Write back to file
        with open(env_path, "w") as f:
            f.writelines(updated_lines)

        return True

    except Exception as e:
        log(f"Error updating .env file: {e}", "ERROR")
        return False


def extract_notifiarr_key_from_config():
    """Extract Notifiarr API key from config file."""
    config_path = Path("config/notifiarr/notifiarr.conf")

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # Notifiarr stores the API key in the 'apikey' field
        api_key = config.get("apikey", "")
        if api_key:
            return api_key
        return None

    except (json.JSONDecodeError, IOError, OSError):
        return None


def extract_notifiarr_key_from_env():
    """Extract Notifiarr API key from container environment."""
    try:
        result = subprocess.run(
            ["docker", "exec", "notifiarr", "printenv", "DN_API_KEY"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        return None

    except Exception:
        return None


def extract_notifiarr_key_from_logs():
    """Extract Notifiarr API key from container logs."""
    try:
        result = subprocess.run(
            ["docker", "logs", "notifiarr", "--tail", "500"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        logs = result.stdout + result.stderr

        # Look for API key patterns in logs - be conservative to avoid false positives
        for line in logs.split("\n"):
            # Only check lines that explicitly mention API keys
            if "api" in line.lower() and "key" in line.lower():
                # Notifiarr API keys are long alphanumeric strings (typically 40-64 chars)
                # Must start with alphanumeric and maintain consistent format
                matches = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]{39,63}\b', line)
                if matches:
                    # Additional validation: keys shouldn't contain common words or URL patterns
                    for match in matches:
                        lower_match = match.lower()
                        if not any(word in lower_match for word in
                                   ['http', 'https', 'docker', 'container', 'config', 'localhost']):
                            # Verify it's sufficiently random (not a common word)
                            if len(set(match)) > 10:  # At least 10 unique characters
                                return match

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def extract_notifiarr_key():
    """Extract Notifiarr API key from multiple sources."""
    log("Checking for Notifiarr API key...", "INFO")

    # Try different extraction methods in order of reliability
    # 1. Try config file (most reliable)
    api_key = extract_notifiarr_key_from_config()
    if api_key:
        log("Found Notifiarr API key in config file", "SUCCESS")
        return api_key

    # 2. Try container environment
    api_key = extract_notifiarr_key_from_env()
    if api_key:
        log("Found Notifiarr API key in container environment", "SUCCESS")
        return api_key

    # 3. Try logs (least reliable)
    api_key = extract_notifiarr_key_from_logs()
    if api_key:
        log("Found Notifiarr API key in container logs", "SUCCESS")
        return api_key

    log("Could not extract Notifiarr API key", "WARNING")
    log("Configure manually at https://notifiarr.com", "INFO")
    return None


load_env()

PROWLARR_API_KEY = os.environ.get("PROWLARR_API_KEY")
SONARR_API_KEY = os.environ.get("SONARR_API_KEY")
RADARR_API_KEY = os.environ.get("RADARR_API_KEY")
NOTIFIARR_API_KEY = os.environ.get("NOTIFIARR_API_KEY")

# Use localhost if running from host, or container names if running inside docker network
SONARR_URL = "http://localhost:8989"
RADARR_URL = "http://localhost:7878"


def fix_indexers(app_name, base_url, app_api_key, correct_prowlarr_key):
    """Fix Prowlarr indexers in Sonarr/Radarr."""
    log(f"Checking {app_name} indexers...", "INFO")

    headers = {"X-Api-Key": app_api_key}
    try:
        resp = requests.get(f"{base_url}/api/v3/indexer", headers=headers)
        resp.raise_for_status()
        indexers = resp.json()
    except Exception as e:
        log(f"Failed to get indexers from {app_name}: {e}", "ERROR")
        return

    count = 0
    for indexer in indexers:
        # Check if it's a Prowlarr indexer
        fields = indexer.get("fields", [])
        url_field = next((f for f in fields if f["name"] == "baseUrl"), None)
        api_field = next((f for f in fields if f["name"] == "apiKey"), None)

        is_prowlarr = False
        if url_field and "prowlarr" in str(url_field.get("value", "")).lower():
            is_prowlarr = True

        if is_prowlarr:
            current_key = api_field.get("value") if api_field else None
            if current_key != correct_prowlarr_key:
                log(f"Updating API key for indexer: {indexer['name']}", "INFO")
                if api_field:
                    api_field["value"] = correct_prowlarr_key
                else:
                    log(f"Skipping {indexer['name']} - no apiKey field found", "WARNING")
                    continue

                try:
                    # Update the indexer
                    update_resp = requests.put(
                        f"{base_url}/api/v3/indexer/{indexer['id']}",
                        headers=headers,
                        json=indexer
                    )
                    update_resp.raise_for_status()

                    # Test the indexer
                    log(f"Testing indexer: {indexer['name']}", "INFO")
                    test_resp = requests.post(
                        f"{base_url}/api/v3/indexer/test",
                        headers=headers,
                        json=indexer
                    )

                    if test_resp.status_code == 200:
                        log(f"Indexer {indexer['name']} test PASSED", "SUCCESS")
                        count += 1
                    else:
                        log(f"Indexer {indexer['name']} test FAILED: {test_resp.text}", "ERROR")

                except Exception as e:
                    log(f"Failed to update/test {indexer['name']}: {e}", "ERROR")

    if count > 0:
        log(f"Updated {count} indexers in {app_name}", "SUCCESS")
    else:
        log(f"No indexers needed updating in {app_name}", "INFO")


if __name__ == "__main__":
    print("=" * 60)
    log("API Key Sync and Validation", "INFO")
    print("=" * 60)
    print()

    # 1. Check and extract Notifiarr API key if missing
    if not NOTIFIARR_API_KEY:
        log("NOTIFIARR_API_KEY not found in .env", "WARNING")
        extracted_key = extract_notifiarr_key()
        if extracted_key:
            # Ask user if they want to save it
            try:
                response = input("\nSave Notifiarr API key to .env? (yes/no): ").strip().lower()
                if response in ["yes", "y"]:
                    if update_env_file("NOTIFIARR_API_KEY", extracted_key):
                        NOTIFIARR_API_KEY = extracted_key
                        log("Restart Notifiarr container: docker compose restart notifiarr", "INFO")
                else:
                    log("Skipped saving Notifiarr API key", "INFO")
            except KeyboardInterrupt:
                print()
                log("Cancelled by user", "WARNING")
        print()
    else:
        log("NOTIFIARR_API_KEY found in .env", "SUCCESS")
        print()

    # 2. Sync Prowlarr keys to Sonarr/Radarr
    if not PROWLARR_API_KEY:
        log("PROWLARR_API_KEY missing - cannot sync indexers", "ERROR")
        sys.exit(1)

    if SONARR_API_KEY:
        fix_indexers("Sonarr", SONARR_URL, SONARR_API_KEY, PROWLARR_API_KEY)
    else:
        log("SONARR_API_KEY missing", "WARNING")

    if RADARR_API_KEY:
        fix_indexers("Radarr", RADARR_URL, RADARR_API_KEY, PROWLARR_API_KEY)
    else:
        log("RADARR_API_KEY missing", "WARNING")

    print()
    log("API key sync complete", "SUCCESS")
