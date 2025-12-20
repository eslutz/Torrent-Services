# Healthchecks & Monitoring

## Overview
This folder contains healthcheck scripts for all services (*arr, qBittorrent, Gluetun, etc.), a generic SQLite/file lock monitor, and shared utilities for logging and notification.


## Multi-service DB/file lock monitoring
- **Config:** `/scripts/healthchecks/monitors.json` lists all services and DBs/files to monitor.
- **Runner:** `/scripts/healthchecks/monitor.sh` reads config and launches a monitor loop for each job.
- **Compose service:** `health-monitor` runs the monitor in a dedicated container (see `docker-compose.yml`).
- **Requirements:** The monitor container must have `jq` installed for JSON parsing.

## Adding a new service to monitor
1. Add a new entry to `/scripts/healthchecks/monitors.json`:
   ```json
   {
     "service": "newservice",
     "type": "sqlite",
     "db": "/config/newservice/db.sqlite",
     "check_interval": 30
   }
   ```
2. Ensure the DB path is correct and accessible in the monitor container.
3. Restart the `sqlite-monitor` container.

## How it works
- Each monitor job runs `/scripts/sqlite_healthcheck.sh monitor` with appropriate env vars.
- The healthcheck script detects lock files and DB errors, attempts safe remediation, and emits structured JSON events to stdout and log files.
- Remediation requests are logged and emailed; container restarts are performed by host-side agents (e.g., autoheal).

## Requirements for monitor container
- Must have `jq`, `sqlite3`, and `mail`/`sendmail` installed for full functionality.
- Example install (Debian):
  ```sh
  apt-get update && apt-get install -y jq sqlite3 mailutils
  ```

## Example Compose service
```
  health-monitor:
    image: debian:stable-slim
    container_name: health-monitor
    restart: unless-stopped
    volumes:
      - ./config:/config:rw
      - ./scripts/healthchecks:/scripts:ro
    networks:
      - torrent-services-network
    command: ["sh", "/scripts/monitor.sh"]
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "2"
```


## File lock monitoring (macOS compatible)
- Add a job to `monitors.json` with type `filelock` and specify the file path:
  ```json
  {
    "service": "qbittorrent",
    "type": "filelock",
    "file": "/config/qbittorrent/qBittorrent/lockfile",
    "check_interval": 30
  }
  ```
- The monitor runner will call `filelock_healthcheck.sh` for each filelock job, which uses `lsof` and `stat` (macOS compatible) to detect and remediate stale locks, and integrates with logging/email.

## Metrics Export

- Run `metrics_exporter.sh` to generate Prometheus metrics from healthcheck logs:
  ```sh
  sh /scripts/healthchecks/metrics_exporter.sh > /config/healthcheck_metrics.prom
  ```
- Example metrics:
  ```
  healthcheck_healthy_total{service="bazarr"} 42
  healthcheck_unhealthy_total{service="bazarr"} 3
  healthcheck_remediation_requested_total{service="bazarr"} 2
  healthcheck_dry_run_total{service="bazarr"} 1
  healthcheck_status{service="bazarr"} 1
  ```
- Scrape `/config/healthcheck_metrics.prom` with Prometheus node exporter or custom scrape config.

## Email Notification
- All notification emails are sent to the address in the `EMAIL_TO` environment variable (set in `.env`).
- To change the recipient, update `EMAIL_TO` in `.env` and restart the monitor container.

## Filelock Monitoring
- Each filelock job in `monitors.json` can specify `lock_age_threshold` (seconds).
- The monitor will check for locks older than the threshold and attempt remediation (remove file).

## Troubleshooting
- Check logs in `/config/<service>/log/healthcheck.log` and container stdout.
- Ensure monitor container has required tools installed.
- For email alerts, configure MTA as described in `SETUP-MTA-macos.md`.
