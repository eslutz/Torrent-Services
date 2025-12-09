import re
import sys
from common import Config, QBitClient

def categorize_torrents():
    config = Config()
    client = QBitClient(config)
    
    if not client.login():
        print("Failed to login to qBittorrent")
        sys.exit(1)
        
    torrents = client.get_torrents()
    print(f"Found {len(torrents)} torrents")
    
    # Regex for TV shows (S01E01, 1x01, Season 1)
    tv_regex = re.compile(r'(S\d+E\d+|S\d+|\d+x\d+|Season\s*\d+)', re.IGNORECASE)
    
    updates = 0
    for torrent in torrents:
        name = torrent.get("name", "")
        current_category = torrent.get("category", "")
        hash_id = torrent.get("hash")
        
        new_category = "movies"
        if tv_regex.search(name):
            new_category = "tv"
        
        if current_category != new_category:
            print(f"Categorizing '{name}' as '{new_category}' (was '{current_category}')")
            try:
                # QBitClient doesn't have set_category method, so we use the session directly
                url = f"{config.base_url}/api/v2/torrents/setCategory"
                client.session.post(url, data={"hashes": hash_id, "category": new_category})
                updates += 1
            except Exception as e:
                print(f"Failed to set category for {name}: {e}")
        else:
            # print(f"Skipping '{name}', already '{current_category}'")
            pass
            
    print(f"Updated categories for {updates} torrents")

if __name__ == "__main__":
    categorize_torrents()
