# Utility Scripts

## manage_storage.py

This script automates the process of adding or removing storage volumes for the torrent services stack. It handles configuration updates across Docker, environment variables, and the applications themselves.

### Features

*   **Automated Configuration**: Updates `.env` and `docker-compose.yml` to mount new drives.
*   **Service Integration**: Adds/Removes root folders in Sonarr and Radarr.
*   **qBittorrent Management**: Updates save paths and migrates active/incomplete downloads to the new storage location.
*   **Zero Downtime**: Automatically restarts containers to apply volume changes.

### Usage

**Add a New Drive**

Provide the absolute path to the mount point on the host machine. The script will automatically assign it a mount point inside the containers (e.g., `/media2`, `/media3`).

```bash
python3 scripts/utilities/manage_storage.py --path /Volumes/NewDrive --action add
```

**Remove a Drive**

Provide the same path used when adding the drive.

```bash
python3 scripts/utilities/manage_storage.py --path /Volumes/NewDrive --action remove
```

### Workflow

**On Add:**
1.  **Environment**: Scans `.env` for the next available `DATA_DIR_X` index and adds the new path.
2.  **Docker**: Updates `docker-compose.yml` to mount the new path to `qbittorrent`, `sonarr`, `radarr`, and `bazarr`.
3.  **Restart**: Restarts containers to apply the new mounts.
4.  **Apps**:
    *   Adds the new TV path to Sonarr.
    *   Adds the new Movies path to Radarr.
    *   Updates qBittorrent to save new downloads to the new drive.
    *   Moves any **incomplete/active** downloads to the new drive to prevent filling up the old storage.

**On Remove:**
1.  **Environment**: Removes the corresponding `DATA_DIR_X` variable from `.env`.
2.  **Docker**: Removes the volume mount from `docker-compose.yml`.
3.  **Restart**: Restarts containers.
4.  **Apps**:
    *   Removes the root folder from Sonarr and Radarr.
    *   Reverts qBittorrent save paths to the default `/media`.
    *   Moves any **incomplete/active** downloads back to `/media`.

## vpn_speedtest.py

This script performs a manual VPN sanity check and throughput test from inside the qBittorrent container. It compares the host's public IP with the container's public IP to confirm VPN egress and runs a download/upload speed test.

### Features

*   **VPN Verification**: Compares Host IP vs Container IP to ensure traffic is routed through the VPN.
*   **Precision Speed Test**: Uses `curl`'s internal JSON metrics for accurate throughput measurement (no text parsing).
*   **JSON Output**: Supports `--json` flag for machine-readable output, useful for monitoring dashboards.
*   **Customizable**: CLI arguments to specify container name and test file sizes.

### Usage

**Standard Run:**

```bash
python3 scripts/utilities/vpn_speedtest.py
```

**Custom Options:**

```bash
# Test with larger files or different container
python3 scripts/utilities/vpn_speedtest.py --dl-size 1GB --ul-size 50MB --container gluetun
```

**JSON Output (for automation):**

```bash
python3 scripts/utilities/vpn_speedtest.py --json
```

**Example Output:**

```text
==========================================
VPN Speed Test: qbittorrent
==========================================

--- 🔒 VPN Status ---
Host IP:      1.2.3.4
Container IP: 5.6.7.8
Status:       SECURE (IPs differ)
Location:     Amsterdam, NL (Mullvad)

--- 🚀 Speed Test ---
Download (100MB):  850.50 Mbps [1s]
Upload (25MB):    120.20 Mbps [2s]

==========================================
```

## check_torrent_status.py

View the status of your torrents directly from the terminal.

### Usage

*   **List all torrents:**
    ```bash
    python3 scripts/utilities/check_torrent_status.py
    ```

*   **Inspect a specific torrent:**
    ```bash
    python3 scripts/utilities/check_torrent_status.py inspect --query "Matrix"
    ```

*   **Analyze stalled torrents:**
    ```bash
    python3 scripts/utilities/check_torrent_status.py stalled
    ```

## manage_torrents.py

Perform actions to fix or manage torrents.

### Usage

*   **Fix Save Paths:**
    Updates torrents with incorrect paths (e.g., `/downloads/incomplete`) to the default save path.
    ```bash
    python3 scripts/utilities/manage_torrents.py fix-paths
    ```

*   **Delete Broken Torrents:**
    Deletes stalled torrents that have no working trackers.
    ```bash
    python3 scripts/utilities/manage_torrents.py delete-broken
    ```

## rescan_missing_media.py

Rescan Sonarr/Radarr libraries to detect missing files and optionally trigger automatic searches to re-download them.

### Features

*   **Detects Missing Media**: Compares database records against actual files on disk
*   **Progress Tracking**: Shows before/after missing counts and waits for completion
*   **Automatic Search**: Optionally queues downloads for missing episodes/movies
*   **Selective Service**: Can target Sonarr, Radarr, or both

### Usage

> **Note:** Use `venv/bin/python3` instead of `python3` when running locally outside Docker.

*   **Rescan both services (detect only):**
    ```bash
    venv/bin/python3 scripts/utilities/rescan_missing_media.py
    ```

*   **Rescan and auto-search for missing:**
    ```bash
    venv/bin/python3 scripts/utilities/rescan_missing_media.py --search
    ```

*   **Rescan only Sonarr:**
    ```bash
    venv/bin/python3 scripts/utilities/rescan_missing_media.py --service sonarr --search
    ```

*   **Rescan only Radarr:**
    ```bash
    venv/bin/python3 scripts/utilities/rescan_missing_media.py --service radarr --search
    ```

### When to Use

*   Files deleted from disk but still marked as downloaded in Sonarr/Radarr
*   After restoring from backup
*   After moving media between drives
*   Periodic maintenance to verify library integrity

### Alternative Methods

**UI Method:**
- **Sonarr:** System → Tasks → Scan Library Files → Run, then Wanted → Missing → Search All
- **Radarr:** System → Tasks → Update Movie Library → Run, then Movies → Missing → Search All

**API Method:**
```bash
# Load environment variables first
source .env

# Sonarr: Rescan library
curl -X POST "http://localhost:8989/api/v3/command" \
  -H "X-Api-Key: $SONARR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "RescanSeries"}'

# Sonarr: Search for missing (after rescan completes)
curl -X POST "http://localhost:8989/api/v3/command" \
  -H "X-Api-Key: $SONARR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "MissingEpisodeSearch"}'

# Radarr: Rescan library
curl -X POST "http://localhost:7878/api/v3/command" \
  -H "X-Api-Key: $RADARR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "RescanMovie"}'

# Radarr: Search for missing (after rescan completes)
curl -X POST "http://localhost:7878/api/v3/command" \
  -H "X-Api-Key: $RADARR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "MissingMoviesSearch"}'
```

### Prevention Settings

Enable these to automatically detect missing files:

**Sonarr:** Settings → Media Management
- ✓ Scan Series Folder After Refresh
- ✓ Rescan Series Folder After Refresh
- ✓ Unmonitor Deleted Episodes

**Radarr:** Settings → Media Management
- ✓ Scan Movie Folder
- ✓ Rescan Movie Folder After Refresh
- ✓ Unmonitor Deleted Movies

## check_qbittorrent_config.py

Dumps the current qBittorrent preferences to the console. Useful for verifying settings or debugging configuration issues.

### Usage

```bash
python3 scripts/utilities/check_qbittorrent_config.py
```

## extract_notifiarr_key.py

Extracts the Notifiarr API key from the container's config file, environment, or logs. Useful for recovering the API key when it's been configured in the Notifiarr web UI but not saved to `.env`.

### Usage

```bash
python3 scripts/utilities/extract_notifiarr_key.py
```

The script will:
1. Check the Notifiarr config file (`config/notifiarr/notifiarr.conf`)
2. Check the container's environment variables
3. Check recent container logs for API key references
4. Prompt to save the extracted key to `.env` file

### When to Use

- After configuring Notifiarr through its web UI
- When the API key is configured but not in `.env`
- When restoring from a backup and API key is missing
- For troubleshooting Notifiarr authentication issues

### Alternative Methods

**Manual extraction from config:**
```bash
# View the config file
cat config/notifiarr/notifiarr.conf | grep apikey
```

**Check container environment:**
```bash
docker exec notifiarr printenv DN_API_KEY
```

