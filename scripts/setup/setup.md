# Setup Scripts

This directory contains Python scripts and configuration files for automating the setup of the Torrent Services stack (Prowlarr, Sonarr, Radarr, Bazarr, qBittorrent).

## Files

- **`setup_prowlarr.py`**: Configures Prowlarr indexers, proxies, and application links.
- **`setup_sonarr.py`**: Configures Sonarr media management, naming, root folders, and download clients.
- **`setup_radarr.py`**: Configures Radarr media management, naming, root folders, and download clients.
- **`setup_bazarr.py`**: Configures Bazarr providers and links to Sonarr/Radarr.
- **`setup_qbittorrent.py`**: Configures qBittorrent authentication and preferences.
- **`setup.config.json`**: The central configuration file defining settings for all services.

## Prerequisites

1.  **Environment Variables**: The scripts rely on the `.env` file in the project root.
    -   API Keys: `PROWLARR_API_KEY`, `SONARR_API_KEY`, `RADARR_API_KEY`, `BAZARR_API_KEY`.
    -   Credentials: `QBIT_USER`, `QBIT_PASS`.
    -   Secrets: e.g., `IPTORRENTS_COOKIE`.
2.  **Python Dependencies**:
    -   `requests` library is required.
    ```bash
    pip install requests
    ```

## Configuration (`setup.config.json`)

The configuration file is divided into sections for each service.

### Structure

```json
{
    "prowlarr": {
        "url": "http://localhost:9696",
        "indexers": [ ... ]
    },
    "sonarr": {
        "url": "http://localhost:8989",
        "media_management": { ... },
        "naming": { ... },
        "root_folders": [ ... ],
        "download_clients": [ ... ]
    },
    "radarr": {
        "url": "http://localhost:7878",
        "media_management": { ... },
        "naming": { ... },
        "root_folders": [ ... ],
        "download_clients": [ ... ]
    },
    "bazarr": {
        "url": "http://localhost:6767",
        "general": { ... }
    },
    "qbittorrent": {
        "url": "http://localhost:8080",
        "preferences": { ... }
    }
}
```

### Key Sections

-   **Prowlarr Indexers**: Defines indexers, priorities, and secrets (mapped to `.env`).
-   **Sonarr/Radarr Naming**: Defines file and folder naming formats.
-   **Download Clients**: Configures the connection to qBittorrent (using `.env` credentials).
-   **qBittorrent Preferences**: Sets internal qBittorrent settings (e.g., paths, limits).

## Usage

### Automatic (Recommended)

The setup scripts are automatically executed by the main bootstrap script in the correct order:

```bash
./scripts/bootstrap.sh
```

### Manual Execution

You can run individual scripts manually if needed. Ensure your `.env` variables are loaded.

```bash
# Load env vars
export $(grep -v '^#' .env | xargs)

# Run specific setup
python3 scripts/setup/setup_sonarr.py
```
