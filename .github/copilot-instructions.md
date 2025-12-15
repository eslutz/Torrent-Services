# Copilot Instructions for Torrent Services

## Naming Conventions

**Markdown files**: Use lowercase with hyphens as separators (e.g., `network-design.md`, `vpn-guide.md`). Exceptions: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`.

## Critical Architecture Patterns

**VPN Network Sharing**: qBittorrent uses `network_mode: "service:gluetun"` to share Gluetun's network namespace. Access qBit at `gluetun:8080` in service configs, not `qbittorrent:8080`.

**Health-Gated Startup**: Services wait for `service_healthy` before starting. Health checks verify real API responses (<5s latency), not just process existence. See `scripts/healthchecks/*.sh` for shell-based probes.

**Bazarr Config Persistence**: Bazarr's API doesn't reliably persist settings. Use direct YAML (`config/bazarr/config/config.yaml`) + SQLite (`config/bazarr/db/bazarr.db`) modification in `setup_bazarr.py`, then restart container.

## Bootstrap Workflow

Run once after `docker compose up -d`:

```bash
docker compose --profile bootstrap up
```

**Execution order**: Wait for healthy → extract API keys from XML configs → setup auth via Playwright → configure inter-service connections → optionally start monitoring exporters.

**Config source of truth**: `scripts/setup/setup.config.json` (service settings) + `.env` (secrets). Bootstrap is idempotent—safe to re-run.

## Development Essentials

**Tests**: `pytest` (min 60% coverage enforced). Mirror `scripts/` structure. Use `unittest.mock` + `responses` for HTTP mocking.

**Code style**: Black (line-length=100), Pylint (max-line-length=100). Run `black .` before committing.

**Env var pattern**: All Python scripts use `from common import load_env; load_env()` to support both Docker (service names) and host (localhost) execution.

**API key extraction**: Services generate random keys on first start → saved to XML → extracted via `xml.etree.ElementTree` → appended to `.env` (no duplicates).

## Docker Compose Patterns

**Resource limits**: Always use env vars with defaults: `mem_limit: ${SERVICE_MEM_LIMIT:-256m}`. Never hardcode.

**Security**: All services use `security_opt: [no-new-privileges:true]`, `init: true`, and 30s grace periods.

**Volume mounts**: Scripts are read-only (`:ro`), configs are bind mounts, ephemeral data uses named volumes (`gluetun-tmp`).

## Common Issues

- **Service won't start**: Check `docker ps --format "table {{.Names}}\t{{.Status}}"` for health status. Run health check manually: `docker exec <container> sh /scripts/<service>.sh`
- **Bootstrap fails**: Ensure services are `healthy` (not just `running`). Check XML config exists and has correct PUID:PGID (1000:1000).
- **Port forwarding**: Verify Gluetun port file: `docker exec gluetun cat /tmp/gluetun/forwarded_port`. Check Forwardarr logs: `docker logs forwardarr --tail 20`

See `scripts/setup/README.md` and `scripts/troubleshooting/troubleshooting.md` for detailed workflows.
