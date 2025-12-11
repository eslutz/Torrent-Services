import os
import sys
import requests
import time

# Add current directory to sys.path to import common
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    load_env,
    log,
    get_api_key,
    wait_for_service,
    configure_config_endpoint,
    configure_root_folders,
    get_headers,
)

load_env()


def trigger_command(url, api_key, command_name, **kwargs):
    log(f"Triggering command: {command_name}", "INFO")
    headers = get_headers(api_key)
    payload = {"name": command_name, **kwargs}
    try:
        resp = requests.post(f"{url}/api/v3/command", headers=headers, json=payload)
        resp.raise_for_status()
        log(f"Command {command_name} triggered", "SUCCESS")
    except Exception as e:
        log(f"Failed to trigger {command_name}: {e}", "ERROR")


def main():
    # Sonarr Config
    sonarr_url = "http://localhost:8989"
    sonarr_api_key = get_api_key("SONARR_API_KEY")

    wait_for_service(sonarr_url, sonarr_api_key, "Sonarr")

    # 1. Add Root Folder
    configure_root_folders(sonarr_url, sonarr_api_key, [{"path": "/media/TV Shows"}])

    # 2. Configure Media Management (Hardlinks)
    configure_config_endpoint(
        sonarr_url,
        sonarr_api_key,
        "mediamanagement",
        {"copyUsingHardlinks": True, "importExtraFiles": True, "extraFileExtensions": "srt,nfo"},
        "Media Management",
    )

    # 3. Trigger DownloadedEpisodesScan (Import existing torrents)
    trigger_command(sonarr_url, sonarr_api_key, "DownloadedEpisodesScan", path="/media/downloads")

    # Radarr Config
    radarr_url = "http://localhost:7878"
    radarr_api_key = get_api_key("RADARR_API_KEY")

    wait_for_service(radarr_url, radarr_api_key, "Radarr")

    # 1. Add Root Folder
    configure_root_folders(radarr_url, radarr_api_key, [{"path": "/media/Movies"}])

    # 2. Configure Media Management (Hardlinks)
    configure_config_endpoint(
        radarr_url,
        radarr_api_key,
        "mediamanagement",
        {"copyUsingHardlinks": True, "importExtraFiles": True, "extraFileExtensions": "srt,nfo"},
        "Media Management",
    )

    # 3. Trigger DownloadedMoviesScan (Import existing torrents)
    trigger_command(radarr_url, radarr_api_key, "DownloadedMoviesScan", path="/media/downloads")


if __name__ == "__main__":
    main()
