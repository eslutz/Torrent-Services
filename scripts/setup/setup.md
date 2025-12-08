# Setup Scripts

This directory contains Python scripts and configuration files for automating the setup of the Torrent Services stack (Prowlarr, Sonarr, Radarr, Bazarr, qBittorrent).

## Files

- **`bootstrap.py`**: The main orchestrator script that runs health checks, extracts keys, and executes service setup scripts.
- **`extract_api_keys.py`**: Extracts API keys from service configuration files and saves them to `.env`.
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

### Automatic (recommended)

The setup scripts run via the bootstrap orchestrator inside Docker Compose and are safe to re-run (idempotent):

```bash
docker compose --profile bootstrap up bootstrap
```

This waits for services to be healthy, extracts API keys into `.env`, and configures inter-service links.

### Manual execution

You can run individual scripts manually if needed. Ensure your `.env` variables are loaded.

```bash
# Load env vars
export $(grep -v '^#' .env | xargs)

# Run specific setup
python3 scripts/setup/setup_sonarr.py
```

## What the bootstrap orchestrator does

- Zero-config in Git: services generate configs and API keys on first boot; secrets stay out of Git.
- Waits for health, reads API keys from configs, writes them to `.env`, and runs the service setup scripts.
- Configures authentication and all inter-service connections (Prowlarr↔Sonarr/Radarr, Sonarr/Radarr→qBittorrent, Bazarr→Sonarr/Radarr).

## Authentication and API keys

| Service | Auth source | API key location | .env variable |
|---------|-------------|------------------|---------------|
| qBittorrent | `QBIT_USER` / `QBIT_PASS` | N/A (cookie-based) | N/A |
| Sonarr | `SONARR_USER` / `SONARR_PASS` | `config/sonarr/config.xml` | `SONARR_API_KEY` |
| Radarr | `RADARR_USER` / `RADARR_PASS` | `config/radarr/config.xml` | `RADARR_API_KEY` |
| Prowlarr | `PROWLARR_USER` / `PROWLARR_PASS` | `config/prowlarr/config.xml` | `PROWLARR_API_KEY` |
| Bazarr | `BAZARR_USER` / `BAZARR_PASS` | `config/bazarr/config/config.yaml` | `BAZARR_API_KEY` |

Saved keys are reused by Prowlarr, Bazarr, and monitoring exporters.

## Service connections configured

- Prowlarr → Sonarr/Radarr (apps) using each app's API key.
- Sonarr/Radarr → qBittorrent download client using `QBIT_USER`/`QBIT_PASS`.
- Bazarr → Sonarr/Radarr using their API keys.

## Re-running bootstrap

The orchestrator is idempotent; re-run the compose command any time to pick up new keys or credentials, or after deleting connections:

```bash
docker compose --profile bootstrap up bootstrap
```

## Verification

- Prowlarr UI: Settings → Apps shows Sonarr and Radarr.
- Sonarr/Radarr UI: Settings → Download Clients shows qBittorrent (tests green).
- Bazarr UI: Settings shows Sonarr/Radarr connected.
- Optional end-to-end: search and grab an item; confirm it lands in qBittorrent with the right category.

## Troubleshooting

- Check container health: `docker compose ps`.
- Inspect logs for failures: `docker compose logs <service> --tail 100`.
- Confirm API keys exist in configs (`config/*/config.xml` or `bazarr/config.yaml`) and in `.env`.
- Re-run the bootstrap compose command after fixing credentials or deleting stale connections.
