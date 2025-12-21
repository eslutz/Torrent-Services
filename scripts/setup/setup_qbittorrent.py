import os
import sys
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load_env, load_config, log, get_api_key, QBitClient

load_env()

CONFIG = load_config()
QBIT_CONFIG = CONFIG.get("qbittorrent", {})
QBIT_URL = os.environ.get("QBIT_URL", QBIT_CONFIG.get("url", "http://localhost:8080"))

def authenticate():
    target_user = get_api_key("SERVICE_USER")
    target_pass = get_api_key("QBITTORRENT_PASSWORD")

    log("Checking qBittorrent authentication status...", "INFO")

    # 1. Try target credentials
    log("Checking if .env credentials are already configured...", "INFO")
    client = QBitClient(QBIT_URL, target_user, target_pass)
    if client.login():
        log("Authenticated with .env credentials", "SUCCESS")
        return client

    log(
        "Could not authenticate with qBittorrent using .env credentials. Ensure setup_auth.py ran successfully.",
        "ERROR",
    )
    sys.exit(1)

def update_credentials(client, new_user, new_pass):
    log("Updating qBittorrent credentials to match .env...", "INFO")

    try:
        # Disable auth subnet whitelist to ensure we don't get locked out
        client.set_preferences({"bypass_auth_subnet_whitelist_enabled": False})

        payload = {"web_ui_username": new_user, "web_ui_password": new_pass}
        
        if client.set_preferences(payload):
            log("Credentials updated successfully", "SUCCESS")
            # Re-login with new credentials
            client.username = new_user
            client.password = new_pass
            client.logged_in = False # Force re-login
            if not client.login():
                log("Failed to login with new credentials after update", "ERROR")
                sys.exit(1)
        else:
            log("Failed to update credentials", "ERROR")
            sys.exit(1)

    except Exception as e:
        log(f"Error updating credentials: {e}", "ERROR")
        sys.exit(1)

def configure_preferences(client):
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

    if client.set_preferences(safe_prefs):
        log("Preferences configured successfully", "SUCCESS")
    else:
        log("Failed to configure preferences", "ERROR")

def configure_categories(client):
    """Configure qBittorrent categories with save paths."""
    log("Configuring qBittorrent categories...", "INFO")
    
    categories = {
        "movies": "/media/downloads/movies",
        "tv shows": "/media/downloads/tv shows"
    }
    
    existing_cats = client.get_categories()
    success_count = 0
    
    for category, save_path in categories.items():
        if category in existing_cats:
            log(f"Category '{category}' exists, verifying save path...", "INFO")
            # Update save path in case it changed
            if client.set_category_save_path(category, save_path):
                log(f"Category '{category}' save path verified: {save_path}", "SUCCESS")
                success_count += 1
            else:
                log(f"Failed to update save path for '{category}'", "ERROR")
        else:
            log(f"Creating category '{category}'...", "INFO")
            if client.create_category(category):
                if client.set_category_save_path(category, save_path):
                    log(f"Category '{category}' created with save path: {save_path}", "SUCCESS")
                    success_count += 1
                else:
                    log(f"Category created but failed to set save path", "ERROR")
            else:
                log(f"Failed to create category '{category}'", "ERROR")
    
    if success_count == len(categories):
        log("All categories configured successfully", "SUCCESS")
    else:
        log(f"Configured {success_count}/{len(categories)} categories", "WARNING")

def wait_for_qbittorrent():
    log("Waiting for qBittorrent...", "INFO")
    import requests
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

    client = authenticate()

    configure_preferences(client)
    
    configure_categories(client)

    log("qBittorrent setup completed successfully", "SUCCESS")

if __name__ == "__main__":
    main()
