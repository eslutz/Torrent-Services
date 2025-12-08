import os
import json
import requests
import sys
import time
import subprocess
import re

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
QBIT_CONFIG = CONFIG.get("qbittorrent", {})
QBIT_URL = os.environ.get("QBIT_URL", QBIT_CONFIG.get("url", "http://localhost:8080"))

def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m"
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")

def get_env_var(var_name):
    val = os.environ.get(var_name)
    if not val:
        log(f"{var_name} not set in environment", "ERROR")
        sys.exit(1)
    return val

def get_qbittorrent_temp_password():
    try:
        # Run docker logs command
        result = subprocess.check_output(["docker", "logs", "qbittorrent"], stderr=subprocess.STDOUT)
        logs = result.decode("utf-8")
        
        # Find the temporary password
        match = re.search(r"temporary password is provided for this session: ([A-Za-z0-9]+)", logs)
        if match:
            return match.group(1)
    except Exception as e:
        log(f"Failed to check docker logs: {e}", "WARNING")
    return None

def login(username, password):
    try:
        session = requests.Session()
        resp = session.post(f"{QBIT_URL}/api/v2/auth/login", data={"username": username, "password": password})
        
        if resp.status_code == 200 and resp.text != "Fails.":
            # Verify login by checking version
            try:
                v_resp = session.get(f"{QBIT_URL}/api/v2/app/version")
                if v_resp.status_code == 200:
                    return session
            except:
                pass
    except Exception as e:
        pass
    return None

def authenticate():
    target_user = get_env_var("QBIT_USER")
    target_pass = get_env_var("QBIT_PASS")
    
    log("Checking qBittorrent authentication status...", "INFO")
    
    # 1. Try target credentials
    log("Checking if .env credentials are already configured...", "INFO")
    session = login(target_user, target_pass)
    if session:
        log("Authenticated with .env credentials", "SUCCESS")
        return session
        
    # 2. Try temp password
    temp_pass = get_qbittorrent_temp_password()
    if temp_pass:
        log(f"Found temporary password: {temp_pass}", "INFO")
        session = login("admin", temp_pass)
        if session:
            log("Authenticated with temporary password", "SUCCESS")
            update_credentials(session, target_user, target_pass)
            return session
    else:
        log("No temporary password found in logs", "INFO")
        
    log("Could not authenticate with qBittorrent using any known credentials", "ERROR")
    sys.exit(1)

def update_credentials(session, new_user, new_pass):
    log("Updating qBittorrent credentials to match .env...", "INFO")
    
    # Disable authentication bypass (must be off to set credentials)
    # WebUI\AuthSubnetWhitelistEnabled=false
    # But the API expects json for setPreferences
    
    # Note: The bootstrap script used:
    # curl ... /api/v2/app/setPreferences --data "json={\"bypass_auth_subnet_whitelist_enabled\":false}"
    
    try:
        # Disable auth bypass
        session.post(f"{QBIT_URL}/api/v2/app/setPreferences", data={"json": json.dumps({"bypass_auth_subnet_whitelist_enabled": False})})
        
        # Update credentials
        # The bootstrap script used:
        # curl ... /api/v2/app/setPreferences --data "json={\"web_ui_username\":\"$new_user\", \"web_ui_password\":\"$new_pass\"}"
        # Wait, qBittorrent API for password change might be different or via preferences.
        # Checking bootstrap script again...
        # It uses /api/v2/app/setPreferences with web_ui_username and web_ui_password in the JSON.
        
        payload = {
            "web_ui_username": new_user,
            "web_ui_password": new_pass
        }
        
        resp = session.post(f"{QBIT_URL}/api/v2/app/setPreferences", data={"json": json.dumps(payload)})
        
        if resp.status_code == 200:
            log("Credentials updated successfully", "SUCCESS")
            # Re-login with new credentials to update session
            new_session = login(new_user, new_pass)
            if new_session:
                # Update the session object in place or return it?
                # Since python passes by reference, but we are assigning a new object...
                # We should probably return the new session or just use the new credentials for future requests if needed.
                # But for this script, we just need a valid session.
                # Actually, the session cookie might still be valid for a bit, but better to be safe.
                session.cookies = new_session.cookies
            else:
                log("Failed to login with new credentials after update", "ERROR")
                sys.exit(1)
        else:
            log(f"Failed to update credentials: {resp.status_code} {resp.text}", "ERROR")
            sys.exit(1)
            
    except Exception as e:
        log(f"Error updating credentials: {e}", "ERROR")
        sys.exit(1)

def configure_preferences(session):
    log("Configuring qBittorrent preferences...", "INFO")
    
    prefs = QBIT_CONFIG.get("preferences", {})
    if not prefs:
        log("No preferences found in config", "WARNING")
        return

    # The user provided JSON has "web_ui_username": "GigaFluxin" in preferences.
    # We should ensure we don't overwrite the password with empty if it's not in there, 
    # but setPreferences merges keys, so it should be fine.
    # However, we just set the username/password in update_credentials.
    # If the config has a different username, it might conflict.
    # Let's assume the config matches .env or we prioritize .env for auth.
    
    # Filter out username/password from preferences to avoid resetting them to something else
    # or causing issues if they are not in sync with .env
    safe_prefs = prefs.copy()
    if "web_ui_username" in safe_prefs:
        del safe_prefs["web_ui_username"]
    if "web_ui_password" in safe_prefs:
        del safe_prefs["web_ui_password"]
        
    try:
        resp = session.post(f"{QBIT_URL}/api/v2/app/setPreferences", data={"json": json.dumps(safe_prefs)})
        
        if resp.status_code == 200:
            log("Preferences configured successfully", "SUCCESS")
        else:
            log(f"Failed to configure preferences: {resp.status_code} {resp.text}", "ERROR")
            
    except Exception as e:
        log(f"Error configuring preferences: {e}", "ERROR")

def wait_for_qbittorrent():
    log("Waiting for qBittorrent...", "INFO")
    for _ in range(30):
        try:
            # Just check if port is open/responding
            requests.get(f"{QBIT_URL}")
            return
        except:
            time.sleep(2)
    log("qBittorrent not reachable", "ERROR")
    sys.exit(1)

def main():
    log("Starting qBittorrent setup...", "INFO")
    
    wait_for_qbittorrent()
    
    session = authenticate()
    
    configure_preferences(session)
    
    log("qBittorrent setup completed successfully", "SUCCESS")

if __name__ == "__main__":
    main()
