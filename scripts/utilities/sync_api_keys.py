import os
import sys
import requests

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

load_env()

PROWLARR_API_KEY = os.environ.get("PROWLARR_API_KEY")
SONARR_API_KEY = os.environ.get("SONARR_API_KEY")
RADARR_API_KEY = os.environ.get("RADARR_API_KEY")

# Use localhost if running from host, or container names if running inside docker network
# Since we are running from host (macOS), we need to use localhost and the mapped ports.
# Checking docker-compose.yml for ports...
# Sonarr: 8989:8989
# Radarr: 7878:7878
SONARR_URL = "http://localhost:8989"
RADARR_URL = "http://localhost:7878"

def fix_indexers(app_name, base_url, app_api_key, correct_prowlarr_key):
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
        # Usually ConfigContract is TorznabSettings or NewznabSettings
        # And the URL field contains prowlarr

        fields = indexer.get("fields", [])
        url_field = next((f for f in fields if f["name"] == "baseUrl"), None)
        api_field = next((f for f in fields if f["name"] == "apiKey"), None)

        is_prowlarr = False
        if url_field and "prowlarr" in str(url_field.get("value", "")).lower():
            is_prowlarr = True

        # Also check implementation name just in case
        if "Torznab" in indexer.get("implementation", ""):
             # Torznab usually implies Prowlarr/Jackett
             pass

        if is_prowlarr:
            current_key = api_field.get("value") if api_field else None
            # If key is redacted (********), we assume it might be wrong and overwrite it to be safe
            if current_key != correct_prowlarr_key:
                log(f"Updating API key for indexer: {indexer['name']}", "INFO")
                if api_field:
                    api_field["value"] = correct_prowlarr_key
                else:
                    log(f"Skipping {indexer['name']} - no apiKey field found", "WARNING")
                    continue

                try:
                    # Update the indexer
                    update_resp = requests.put(f"{base_url}/api/v3/indexer/{indexer['id']}", headers=headers, json=indexer)
                    update_resp.raise_for_status()

                    # Test the indexer
                    log(f"Testing indexer: {indexer['name']}", "INFO")
                    # For test, we need to send the object with the new key
                    test_resp = requests.post(f"{base_url}/api/v3/indexer/test", headers=headers, json=indexer)

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
    if not PROWLARR_API_KEY:
        log("PROWLARR_API_KEY missing", "ERROR")
        sys.exit(1)

    if SONARR_API_KEY:
        fix_indexers("Sonarr", SONARR_URL, SONARR_API_KEY, PROWLARR_API_KEY)
    else:
        log("SONARR_API_KEY missing", "WARNING")

    if RADARR_API_KEY:
        fix_indexers("Radarr", RADARR_URL, RADARR_API_KEY, PROWLARR_API_KEY)
    else:
        log("RADARR_API_KEY missing", "WARNING")
