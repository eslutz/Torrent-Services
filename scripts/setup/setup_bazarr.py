import os
import requests
import json
import yaml
import sqlite3
from common import load_env, load_config, log, get_api_key, get_headers

load_env()

CONFIG = load_config()
BAZARR_CONFIG = CONFIG.get("bazarr", {})
BAZARR_URL = os.environ.get("BAZARR_URL", BAZARR_CONFIG.get("url", "http://localhost:6767"))

# Path to Bazarr config file and database
BAZARR_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../../config/bazarr/config/config.yaml")
BAZARR_DB_PATH = os.path.join(os.path.dirname(__file__), "../../config/bazarr/db/bazarr.db")

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

def update_config_yaml():
    """Update the config.yaml file directly with settings from setup.config.json"""
    log("Updating Bazarr config.yaml...", "INFO")

    try:
        # Read existing config
        config_path = os.path.abspath(BAZARR_CONFIG_PATH)
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Update general settings
        general_config = BAZARR_CONFIG.get("general", {})
        for key, value in general_config.items():
            config["general"][key] = value

        # Update sonarr settings
        sonarr_config = BAZARR_CONFIG.get("sonarr", {})
        if sonarr_config:
            sonarr_api_key = os.environ.get("SONARR_API_KEY")
            if sonarr_api_key:
                sonarr_config["apikey"] = sonarr_api_key
            for key, value in sonarr_config.items():
                config["sonarr"][key] = value

        # Update radarr settings
        radarr_config = BAZARR_CONFIG.get("radarr", {})
        if radarr_config:
            radarr_api_key = os.environ.get("RADARR_API_KEY")
            if radarr_api_key:
                radarr_config["apikey"] = radarr_api_key
            for key, value in radarr_config.items():
                config["radarr"][key] = value

        # Write config back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        log("Config.yaml updated successfully", "SUCCESS")
        return True

    except Exception as e:
        log(f"Failed to update config.yaml: {e}", "ERROR")
        return False

def restart_bazarr():
    """Restart Bazarr container to apply config changes"""
    log("Restarting Bazarr to apply configuration...", "INFO")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "compose", "restart", "bazarr"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            log("Bazarr restarted successfully", "SUCCESS")
            # Wait for it to come back up
            import time
            time.sleep(5)
            return True
        else:
            log(f"Failed to restart Bazarr: {result.stderr}", "ERROR")
            return False
    except Exception as e:
        log(f"Failed to restart Bazarr: {e}", "ERROR")
        return False

def configure_language_profiles_db():
    """Configure language profiles by updating the database directly"""
    log("Configuring language profiles in database...", "INFO")
    profiles_config = BAZARR_CONFIG.get("language_profiles", [])

    if not profiles_config:
        log("No language profiles configured", "INFO")
        return True

    try:
        db_path = os.path.abspath(BAZARR_DB_PATH)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get existing profiles
        cursor.execute("SELECT profileId, name FROM table_languages_profiles")
        existing_profiles = {row[1]: row[0] for row in cursor.fetchall()}

        for profile_config in profiles_config:
            profile_name = profile_config["name"]

            # Construct items list as JSON
            items = []
            for idx, lang in enumerate(profile_config.get("languages", [])):
                items.append({
                    "id": idx + 1,
                    "language": lang["language"],
                    "forced": "True" if lang.get("forced", False) else "False",
                    "hi": "True" if lang.get("hi", False) else "False",
                    "audio_exclude": lang.get("audio_exclude", "False")
                })

            items_json = json.dumps(items)

            if profile_name in existing_profiles:
                # Update existing profile
                profile_id = existing_profiles[profile_name]
                cursor.execute(
                    "UPDATE table_languages_profiles SET items = ?, cutoff = 0, mustContain = '', mustNotContain = '', originalFormat = 0, tag = NULL WHERE profileId = ?",
                    (items_json, profile_id)
                )
                log(f"Updated language profile: {profile_name}", "INFO")
            else:
                # Create new profile
                cursor.execute(
                    "INSERT INTO table_languages_profiles (name, items, cutoff, mustContain, mustNotContain, originalFormat, tag) VALUES (?, ?, 0, '', '', 0, NULL)",
                    (profile_name, items_json)
                )
                log(f"Created language profile: {profile_name}", "INFO")

        conn.commit()
        conn.close()
        log("Language profiles configured successfully", "SUCCESS")
        return True

    except Exception as e:
        log(f"Failed to configure language profiles: {e}", "ERROR")
        return False

def main():
    log("Starting Bazarr setup...", "INFO")

    bazarr_api_key = get_api_key("BAZARR_API_KEY")

    wait_for_bazarr(bazarr_api_key)

    # Update config file directly
    if not update_config_yaml():
        import sys
        sys.exit(1)

    # Configure language profiles in database
    if not configure_language_profiles_db():
        import sys
        sys.exit(1)

    # Restart Bazarr to apply all changes
    if not restart_bazarr():
        import sys
        sys.exit(1)

    # Wait for Bazarr to be ready again
    wait_for_bazarr(bazarr_api_key)

    log("Bazarr setup completed successfully", "SUCCESS")

if __name__ == "__main__":
    main()
