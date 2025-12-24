# Healthchecks & Notifications

## Overview
This folder contains healthcheck scripts for all services (*arr, qBittorrent, Gluetun, etc.) and shared utilities for logging/notification. It now also includes a Docker events email notifier (used by the `health-monitor` container) that alerts when containers become unhealthy or stop.

## Email notifications (health-monitor)
- `docker_events_notifier.sh` listens to Docker container events and sends an email when a container reports `unhealthy`, `die`, `stop`, `kill`, or `oom`.
- The `health-monitor` service in `docker-compose.yml` installs `msmtp` + `jq`, mounts the Docker socket read-only, and runs the notifier.
- Configure SMTP via environment variables in `.env`:
  - `EMAIL_TO` (recipient), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- Logs are written to `/logs/health-monitor/events.log` inside the compose stack.
- Autoheal restarts: the notifier also tails `/logs/autoheal/log.json` (configurable via `AUTOHEAL_LOG`) and emails whenever Autoheal restarts a container.

## Per-service healthchecks
- Each service uses `run_healthcheck.sh` with its specific script (e.g., `sonarr.sh`, `radarr.sh`).
- Shared helpers for logging/email live in `healthcheck_utils.sh`.

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

## Troubleshooting
- Check logs in `/logs/<service>/healthcheck.log` and container stdout.
- Ensure the monitor container has required tools installed.
- For email alerts, configure MTA as described in `SETUP-MTA-macos.md`.
