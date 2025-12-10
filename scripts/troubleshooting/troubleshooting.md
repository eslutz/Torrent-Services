# Troubleshooting Scripts

This directory contains a set of Python scripts to help troubleshoot and manage your qBittorrent instance.

## Configuration

1. **Credentials**: The scripts automatically pull `SERVICE_USER` and `QBIT_PASS` from the `.env` file in the project root.
2. **Settings**: Non-secret settings are configured in `troubleshooting.config.json`.
    * `qbittorrent_url`: URL of the Web UI (default: `http://localhost:8080`)
    * `bt_backup_path`: Path to qBittorrent's `BT_backup` folder.
    * `default_save_path`: The correct path where downloads should be saved (e.g., `/media/downloads`).
    * `default_scan_path`: Default path to scan for `.torrent` files to add.

## Scripts

### 1. `check_status.py`

View the status of your torrents.

* **List all torrents:**

    ```bash
    python3 check_status.py
    ```

* **Inspect a specific torrent:**

    ```bash
    python3 check_status.py inspect --query "Matrix"
    ```

* **Analyze stalled torrents:**

    ```bash
    python3 check_status.py stalled
    ```

### 2. `manage_torrents.py`

Perform actions to fix or manage torrents.

* **Fix Save Paths:**
    Updates torrents with incorrect paths (e.g., `/downloads/incomplete`) to the default save path defined in `config.json`.

    ```bash
    python3 manage_torrents.py fix-paths
    ```

* **Delete Broken Torrents:**
    Deletes stalled torrents that have no working trackers.

    ```bash
    python3 manage_torrents.py delete-broken
    # To also delete the files on disk:
    python3 manage_torrents.py delete-broken --delete-files
    ```

* **Add Missing Torrents:**
    Scans a folder for `.torrent` files and adds them to qBittorrent.

    ```bash
    # Scan default folder (configured in troubleshooting.config.json)
    python3 manage_torrents.py add-missing

    # Scan a specific folder
    python3 manage_torrents.py add-missing --path "/path/to/folder"
    ```

* **Force Recheck:**
    Triggers a recheck on all torrents.

    ```bash
    python3 manage_torrents.py recheck
    ```

* **Force Reannounce:**
    Triggers a reannounce to all trackers for all torrents.

    ```bash
    python3 manage_torrents.py announce
    ```

### 3. `inspect_backup.py`

Inspect the raw `.torrent` file from the backup directory to check for metadata issues (like missing announce URLs).

* **Usage:**

    ```bash
    python3 inspect_backup.py <HASH>
    ```

## Common Issues & Fixes

* **"Error" State:** Usually caused by a path mismatch. Run `python3 manage_torrents.py fix-paths`.
* **"Stalled" State:**
    1. Run `python3 check_status.py stalled` to see if trackers are working.
    2. If trackers are "Not working" or "Unregistered", the torrent might be dead or removed from the tracker.
    3. Run `python3 manage_torrents.py delete-broken` to clean them up.
