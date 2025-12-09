import os
import sys
import requests

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import load_env, log, get_api_key

load_env()

def update_sonarr_category():
    sonarr_url = "http://localhost:8989"
    sonarr_api_key = get_api_key("SONARR_API_KEY")
    
    log("Updating Sonarr download client category...", "INFO")
    headers = {"X-Api-Key": sonarr_api_key}
    try:
        # Get clients
        resp = requests.get(f"{sonarr_url}/api/v3/downloadclient", headers=headers)
        resp.raise_for_status()
        clients = resp.json()
        
        qbit_client = next((c for c in clients if c["implementation"] == "QBittorrent"), None)
        if not qbit_client:
            log("qBittorrent client not found in Sonarr", "ERROR")
            return

        # Update field
        updated = False
        for field in qbit_client["fields"]:
            if field["name"] == "tvCategory" and field["value"] != "tv shows":
                field["value"] = "tv shows"
                updated = True
        
        if updated:
            resp = requests.put(f"{sonarr_url}/api/v3/downloadclient/{qbit_client['id']}", headers=headers, json=qbit_client)
            resp.raise_for_status()
            log("Sonarr download client updated to 'tv shows'", "SUCCESS")
        else:
            log("Sonarr download client already set to 'tv shows'", "SUCCESS")
            
    except Exception as e:
        log(f"Failed to update Sonarr: {e}", "ERROR")

def update_qbittorrent_categories():
    qbit_url = "http://localhost:8080"
    username = os.environ.get("SERVICE_USER", "admin")
    password = os.environ.get("QBIT_PASSWORD")
    
    log("Updating qBittorrent categories...", "INFO")
    session = requests.Session()
    try:
        # Login
        session.post(f"{qbit_url}/api/v2/auth/login", data={"username": username, "password": password}).raise_for_status()
        
        # Get torrents
        resp = session.get(f"{qbit_url}/api/v2/torrents/info")
        resp.raise_for_status()
        torrents = resp.json()
        
        updates = 0
        for torrent in torrents:
            if torrent.get("category") == "tv":
                name = torrent.get("name")
                hash_id = torrent.get("hash")
                log(f"Updating '{name}' from 'tv' to 'tv shows'", "INFO")
                session.post(f"{qbit_url}/api/v2/torrents/setCategory", data={"hashes": hash_id, "category": "tv shows"})
                updates += 1
        
        log(f"Updated {updates} torrents in qBittorrent", "SUCCESS")
        
    except Exception as e:
        log(f"Failed to update qBittorrent: {e}", "ERROR")

if __name__ == "__main__":
    update_sonarr_category()
    update_qbittorrent_categories()
