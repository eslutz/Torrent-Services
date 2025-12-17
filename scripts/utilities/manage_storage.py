import os
import sys
import json
import argparse
import requests
import re
import subprocess
import time

# Add scripts directory to sys.path
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(scripts_dir)
from common import load_env, log, get_api_key, wait_for_service, configure_root_folders, get_headers, DEFAULT_TIMEOUT, QBitClient

# We reload env later, but need project root now
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
COMPOSE_FILE = os.path.join(PROJECT_ROOT, "docker-compose.yml")

SONARR_URL = os.environ.get("SONARR_URL", "http://localhost:8989")
RADARR_URL = os.environ.get("RADARR_URL", "http://localhost:7878")

def update_env_file(action, path):
    """Updates .env file to add or remove the storage path variable."""
    log(f"Updating .env file for {action} action...", "INFO")
    
    with open(ENV_FILE, "r") as f:
        lines = f.readlines()

    var_name = None
    mount_point = None
    
    # Normalize path to handle potential trailing slashes or quotes
    target_path = path.strip().rstrip('/')

    if action == "add":
        # Check if path already exists
        for line in lines:
            match = re.match(r'^(DATA_DIR(_(\d+))?)=["\']?([^"\']+)["\']?', line)
            if match:
                current_val = match.group(4).strip().rstrip('/')
                if current_val == target_path:
                    var_name = match.group(1)
                    if match.group(3):
                        mount_point = f"/media{match.group(3)}"
                    else:
                        mount_point = "/media"
                    log(f"Path {path} already exists as {var_name}", "INFO")
                    return var_name, mount_point

        # Find highest DATA_DIR index
        max_index = 1
        for line in lines:
            match = re.match(r'^DATA_DIR(_(\d+))?=', line)
            if match:
                if match.group(2):
                    index = int(match.group(2))
                    if index > max_index:
                        max_index = index
                else:
                    # DATA_DIR implies index 1
                    pass
        
        next_index = max_index + 1
        var_name = f"DATA_DIR_{next_index}"
        mount_point = f"/media{next_index}"
        
        # Append new variable
        new_line = f'{var_name}="{path}"\n'
        
        # Insert after the last DATA_DIR line or at end
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("DATA_DIR"):
                insert_idx = i + 1
        
        lines.insert(insert_idx, new_line)
        log(f"Added {var_name}={path} to .env", "SUCCESS")

    elif action == "remove":
        # Find variable matching the path
        
        new_lines = []
        for line in lines:
            # Check if line is a DATA_DIR assignment
            match = re.match(r'^(DATA_DIR(_(\d+))?)=["\']?([^"\']+)["\']?', line)
            if match:
                current_var = match.group(1)
                current_val = match.group(4).strip().rstrip('/')
                
                if current_val == target_path:
                    var_name = current_var
                    # Determine mount point based on var name
                    if match.group(3):
                        mount_point = f"/media{match.group(3)}"
                    else:
                        mount_point = "/media"
                    log(f"Removing {var_name} from .env", "SUCCESS")
                    continue # Skip adding this line to new_lines
            
            new_lines.append(line)
        lines = new_lines

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)
        
    return var_name, mount_point

def update_docker_compose(action, var_name, mount_point):
    """Updates docker-compose.yml to add or remove volume mounts."""
    log(f"Updating docker-compose.yml...", "INFO")
    
    with open(COMPOSE_FILE, "r") as f:
        lines = f.readlines()

    services_to_update = ['qbittorrent', 'sonarr', 'radarr', 'bazarr']
    new_lines = []
    
    # Pre-check existence for add action
    services_with_volume = set()
    if action == "add":
        current_service = None
        in_vols = False
        for line in lines:
            service_match = re.match(r'^  ([a-zA-Z0-9_-]+):', line)
            if service_match:
                current_service = service_match.group(1)
                in_vols = False
            
            if current_service in services_to_update and line.strip() == "volumes:":
                in_vols = True
            
            if in_vols and (line.strip() == "" or (line.startswith("    ") and not line.startswith("      -"))):
                in_vols = False
                
            if in_vols and f"${{{var_name}}}:{mount_point}" in line:
                services_with_volume.add(current_service)

    # Regex to identify service blocks and volumes section
    in_target_service = False
    in_volumes = False
    service_name = None
    
    # Indentation for the new volume line (usually 6 spaces)
    volume_indent = "      " 
    
    for i, line in enumerate(lines):
        # Detect service start
        service_match = re.match(r'^  ([a-zA-Z0-9_-]+):', line)
        if service_match:
            service_name = service_match.group(1)
            if service_name in services_to_update:
                in_target_service = True
            else:
                in_target_service = False
            in_volumes = False
        
        # Detect volumes section
        if in_target_service and line.strip() == "volumes:":
            in_volumes = True
            new_lines.append(line)
            continue

        # Detect end of volumes section (next property or unindent)
        if in_volumes and (line.strip() == "" or (line.startswith("    ") and not line.startswith("      -"))):
             in_volumes = False

        if in_volumes and action == "add":
            if service_name in services_with_volume:
                new_lines.append(line)
                continue

            # Check if we are at the end of the volumes list for this service
            # We look ahead to see if the next line is not a volume definition
            is_last_volume = False
            if i + 1 < len(lines):
                next_line = lines[i+1]
                if not next_line.strip().startswith("-"):
                    is_last_volume = True
            
            new_lines.append(line)
            
            if is_last_volume:
                # Add the new volume
                # Format: - ${DATA_DIR_X:-/path}:/mediaX
                # We use the var_name only to keep it clean: - ${DATA_DIR_X}:/mediaX
                new_vol = f'{volume_indent}- ${{{var_name}}}:{mount_point}\n'
                new_lines.append(new_vol)
                log(f"Added volume mount to {service_name}", "INFO")
            continue

        if in_volumes and action == "remove":
            # Check if line contains our variable
            if f"${{{var_name}}}" in line or f"${{{var_name}:" in line:
                log(f"Removed volume mount from {service_name}", "INFO")
                continue # Skip this line
        
        new_lines.append(line)

    with open(COMPOSE_FILE, "w") as f:
        f.writelines(new_lines)
    
    log("Updated docker-compose.yml", "SUCCESS")

def restart_containers():
    log("Restarting containers to apply changes...", "INFO")
    try:
        subprocess.run(["docker", "compose", "up", "-d"], cwd=PROJECT_ROOT, check=True)
        log("Containers restarted successfully", "SUCCESS")
        # Give them a moment to start initializing
        time.sleep(5)
    except subprocess.CalledProcessError as e:
        log(f"Failed to restart containers: {e}", "ERROR")
        sys.exit(1)

def remove_root_folder(url, api_key, path, service_name):
    """Remove a root folder from an *arr service."""
    log(f"Removing root folder {path} from {service_name}...", "INFO")
    headers = get_headers(api_key)
    try:
        # Get all root folders
        resp = requests.get(f"{url}/api/v3/rootfolder", headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        root_folders = resp.json()
        
        # Find the folder to remove
        folder_to_remove = next((f for f in root_folders if f["path"] == path), None)
        
        if folder_to_remove:
            # Delete the folder
            del_resp = requests.delete(f"{url}/api/v3/rootfolder/{folder_to_remove['id']}", headers=headers, timeout=DEFAULT_TIMEOUT)
            del_resp.raise_for_status()
            log(f"Removed {path} from {service_name}", "SUCCESS")
        else:
            log(f"Root folder {path} not found in {service_name}", "WARNING")
            
    except requests.exceptions.RequestException as e:
        log(f"Failed to remove root folder from {service_name}: {e}", "ERROR")

def update_qbittorrent_paths(client, base_path):
    downloads_path = f"{base_path}/downloads"
    incomplete_path = f"{base_path}/incomplete"
    log(f"Updating qBittorrent save paths to {downloads_path} and incomplete torrents to {incomplete_path}...", "INFO")

    # Update Default Save Path and Incomplete Torrents Path
    prefs = {
        "save_path": downloads_path,
        "temp_path_enabled": True,
        "temp_path": incomplete_path
    }
    if client.set_preferences(prefs):
        log(f"Updated default save path to {downloads_path} and incomplete torrents path to {incomplete_path}", "SUCCESS")

def move_incomplete_torrents(client, target_base_path):
    log("Checking for active/queued torrents to move...", "INFO")
    try:
        # Get all torrents
        torrents = client.get_torrents()
        
        # Filter for incomplete torrents
        incomplete_torrents = [t for t in torrents if t['amount_left'] > 0]
        
        if not incomplete_torrents:
            log("No active/queued torrents found to move.", "INFO")
            return

        log(f"Found {len(incomplete_torrents)} incomplete torrents. Moving to {target_base_path}...", "INFO")

        target_downloads = f"{target_base_path}/downloads"

        for torrent in incomplete_torrents:
            hash = torrent['hash']
            name = torrent['name']
            current_path = torrent['save_path']
            
            # Recreate existing path structure on new volume
            # e.g. /media/downloads/Movies -> /media2/downloads/Movies
            if "/downloads" in current_path:
                parts = current_path.split("/downloads")
                if len(parts) > 1:
                    # parts[1] will include the leading slash if present in original split, 
                    # but split removes the delimiter.
                    # If path is .../downloads/Movies, parts[1] is /Movies
                    new_path = f"{target_downloads}{parts[1]}"
                else:
                    new_path = target_downloads
            else:
                # Fallback if structure is unexpected
                new_path = target_downloads
            
            # Normalize paths for comparison (remove trailing slashes)
            if os.path.normpath(current_path) == os.path.normpath(new_path):
                continue
                
            log(f"Moving '{name}' from {current_path} to {new_path}...", "INFO")
            
            # setLocation
            client.set_location(hash, new_path)
                
    except Exception as e:
        log(f"Error moving torrents: {e}", "ERROR")

def main():
    parser = argparse.ArgumentParser(description="Manage storage paths for Torrent Services")
    parser.add_argument("--path", required=True, help="The mount point path (e.g., /Volumes/MediaLib3)")
    parser.add_argument("--action", choices=["add", "remove"], default="add", help="Action to perform")
    
    args = parser.parse_args()
    
    # 1. Update .env and docker-compose.yml
    var_name, mount_point = update_env_file(args.action, args.path)
    
    if not var_name or not mount_point:
        if args.action == "remove":
            log(f"Could not find configuration for {args.path} in .env", "ERROR")
            sys.exit(1)
        else:
            log("Failed to determine new variable name or mount point", "ERROR")
            sys.exit(1)

    update_docker_compose(args.action, var_name, mount_point)
    
    # 2. Restart Containers
    restart_containers()
    
    # Reload env to get the new variable if we added it (though we use mount_point directly mostly)
    load_env()
    
    tv_path = f"{mount_point}/TV Shows"
    movies_path = f"{mount_point}/Movies"
    
    if args.action == "add":
        # Use args.path (host path) for creation
        host_tv_path = os.path.join(args.path, "TV Shows")
        host_movies_path = os.path.join(args.path, "Movies")
        
        log(f"Creating directories in {args.path}...", "INFO")
        try:
            os.makedirs(host_tv_path, exist_ok=True)
            os.makedirs(host_movies_path, exist_ok=True)
            log(f"Created {host_tv_path} and {host_movies_path}", "SUCCESS")
        except Exception as e:
            log(f"Failed to create directories: {e}", "ERROR")
            sys.exit(1)
    
    log(f"Starting Storage {args.action.title()} for {mount_point}...", "INFO")

    # 3. Configure Sonarr
    sonarr_key = get_api_key("SONARR_API_KEY")
    if sonarr_key:
        wait_for_service(SONARR_URL, sonarr_key, "Sonarr")
        if args.action == "add":
            configure_root_folders(SONARR_URL, sonarr_key, [{"path": tv_path}])
        else:
            remove_root_folder(SONARR_URL, sonarr_key, tv_path, "Sonarr")
    else:
        log("SONARR_API_KEY not found, skipping Sonarr", "WARNING")

    # 4. Configure Radarr
    radarr_key = get_api_key("RADARR_API_KEY")
    if radarr_key:
        wait_for_service(RADARR_URL, radarr_key, "Radarr")
        if args.action == "add":
            configure_root_folders(RADARR_URL, radarr_key, [{"path": movies_path}])
        else:
            remove_root_folder(RADARR_URL, radarr_key, movies_path, "Radarr")
    else:
        log("RADARR_API_KEY not found, skipping Radarr", "WARNING")

    # 5. Configure qBittorrent
    # Bazarr does not need explicit configuration as it syncs with Sonarr/Radarr
    try:
        qbit_user = os.environ.get("SERVICE_USER", "admin")
        qbit_pass = os.environ.get("QBITTORRENT_PASSWORD")
        qbit_url = os.environ.get("QBIT_URL", "http://localhost:8080")
        
        if not qbit_pass:
             log("QBITTORRENT_PASSWORD not found in env, skipping qBittorrent configuration", "WARNING")
        else:
            client = QBitClient(qbit_url, qbit_user, qbit_pass)
            if client.login():
                if args.action == "add":
                    update_qbittorrent_paths(client, mount_point)
                    move_incomplete_torrents(client, mount_point)
                else:
                    # Revert to default /media path on remove
                    update_qbittorrent_paths(client, "/media")
                    move_incomplete_torrents(client, "/media")
            else:
                log("Failed to authenticate with qBittorrent", "ERROR")
    except Exception as e:
        log(f"Failed to configure qBittorrent: {e}", "ERROR")

    log(f"Storage {args.action} configuration complete!", "SUCCESS")

if __name__ == "__main__":
    main()
