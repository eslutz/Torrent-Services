import os
import json
import requests
import sys
from common import load_env, load_config, log, get_api_key

load_env()

CONFIG = load_config()
QBIT_CONFIG = CONFIG.get("qbittorrent", {})
QBIT_URL = os.environ.get("QBIT_URL", QBIT_CONFIG.get("url", "http://localhost:8080"))

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

def authenticate():
    target_user = get_api_key("SERVICE_USER")
    target_pass = get_api_key("QBIT_PASSWORD")
    
    log("Checking qBittorrent authentication status...", "INFO")
    
    # 1. Try target credentials
    log("Checking if .env credentials are already configured...", "INFO")
    session = login(target_user, target_pass)
    if session:
        log("Authenticated with .env credentials", "SUCCESS")
        return session
        
    log("Could not authenticate with qBittorrent using .env credentials. Ensure setup_auth.py ran successfully.", "ERROR")
    sys.exit(1)

def update_credentials(session, new_user, new_pass):
    log("Updating qBittorrent credentials to match .env...", "INFO")
    
    try:
        session.post(f"{QBIT_URL}/api/v2/app/setPreferences", data={"json": json.dumps({"bypass_auth_subnet_whitelist_enabled": False})})
        
        payload = {
            "web_ui_username": new_user,
            "web_ui_password": new_pass
        }
        
        resp = session.post(f"{QBIT_URL}/api/v2/app/setPreferences", data={"json": json.dumps(payload)})
        
        if resp.status_code == 200:
            log("Credentials updated successfully", "SUCCESS")
            new_session = login(new_user, new_pass)
            if new_session:
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
    import time
    for _ in range(30):
        try:
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
