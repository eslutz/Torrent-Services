import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import (
    load_env,
    load_config,
    log,
    get_api_key,
    wait_for_service,
    disable_analytics,
    configure_config_endpoint,
    configure_download_clients,
    configure_root_folders,
)

load_env()

CONFIG = load_config()
SONARR_CONFIG = CONFIG.get("sonarr", {})
SONARR_URL = os.environ.get("SONARR_URL", SONARR_CONFIG.get("url", "http://localhost:8989"))


def main():
    api_key = get_api_key("SONARR_API_KEY")
    wait_for_service(SONARR_URL, api_key, "Sonarr")
    disable_analytics(SONARR_URL, api_key, "Sonarr")

    configure_config_endpoint(
        SONARR_URL,
        api_key,
        "mediamanagement",
        SONARR_CONFIG.get("media_management"),
        "Media Management",
    )

    configure_config_endpoint(SONARR_URL, api_key, "naming", SONARR_CONFIG.get("naming"), "Naming")

    configure_download_clients(SONARR_URL, api_key, SONARR_CONFIG.get("download_clients", []))

    configure_root_folders(SONARR_URL, api_key, SONARR_CONFIG.get("root_folders", []))


if __name__ == "__main__":
    main()
