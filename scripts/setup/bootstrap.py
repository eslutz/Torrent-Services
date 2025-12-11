import os
import sys
import time
import subprocess
import requests

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
ENV_FILE = os.path.join(PROJECT_DIR, ".env")


def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m",
    }
    print(f"{colors.get(level, '')}[{level}] {msg}{colors['NC']}")


def load_env():
    if os.path.exists(ENV_FILE):
        log("Loading environment variables from .env...", "INFO")
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]

                        if key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            log(f"Warning: Failed to load .env file: {e}", "WARNING")
    else:
        log(f".env file not found at {ENV_FILE}", "ERROR")
        sys.exit(1)


def wait_for_service(name, url):
    log(f"Waiting for {name} to be ready...", "INFO")
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code in [200, 401, 302]:
                log(f"{name} is ready", "SUCCESS")
                return
        except requests.RequestException:
            pass
        time.sleep(2)

    log(f"{name} failed to become ready after {max_attempts} attempts", "ERROR")
    sys.exit(1)


def run_script(script_name):
    script_path = os.path.join(SCRIPT_DIR, script_name)
    log(f"Running {script_name}...", "INFO")
    try:
        # Pass current environment to subprocess
        result = subprocess.run([sys.executable, script_path], env=os.environ, check=True)
        log(f"{script_name} completed", "SUCCESS")
    except subprocess.CalledProcessError:
        log(f"{script_name} failed", "ERROR")
        sys.exit(1)


def main():
    print("")
    print("\033[0;34m╔══════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[0;34m║         Torrent Services Bootstrap Script                    ║\033[0m")
    print("\033[0;34m╚══════════════════════════════════════════════════════════════╝\033[0m")
    print("")

    load_env()

    # Validate required environment variables
    if not os.environ.get("SERVICE_USER"):
        log("SERVICE_USER must be set in .env", "ERROR")
        sys.exit(1)

    # Determine URLs (use env vars if set, else default to localhost for host execution)
    prowlarr_url = os.environ.get("PROWLARR_URL", "http://localhost:9696")
    sonarr_url = os.environ.get("SONARR_URL", "http://localhost:8989")
    radarr_url = os.environ.get("RADARR_URL", "http://localhost:7878")
    bazarr_url = os.environ.get("BAZARR_URL", "http://localhost:6767")
    qbittorrent_url = os.environ.get("QBIT_URL", "http://localhost:8080")

    # Wait for services
    # Note: We use the /ping endpoint where applicable, or root
    wait_for_service("Prowlarr", f"{prowlarr_url}/ping")
    wait_for_service("Sonarr", f"{sonarr_url}/ping")
    wait_for_service("Radarr", f"{radarr_url}/ping")
    wait_for_service("Bazarr", f"{bazarr_url}/ping")
    wait_for_service("qBittorrent", qbittorrent_url)

    # Extract API Keys
    run_script("extract_api_keys.py")

    # Reload env to get the new keys
    load_env()

    # Run Authentication Setup (Playwright)
    run_script("setup_auth.py")

    # Run Setup Scripts
    run_script("setup_qbittorrent.py")
    run_script("setup_prowlarr.py")
    run_script("setup_sonarr.py")
    run_script("setup_radarr.py")
    run_script("setup_bazarr.py")

    # Monitoring
    if os.environ.get("ENABLE_MONITORING_PROFILE", "").lower() in ["true", "1", "yes", "on"]:
        log("Starting Monitoring Stack...", "INFO")

        # Handle Docker-in-Docker volume mounting issues on macOS/Windows
        # We need to tell docker-compose to use the HOST's path for relative volumes,
        # not the container's path (/app), otherwise bind mounts will be empty/broken.
        host_project_dir = os.environ.get("HOST_PROJECT_DIR")
        env = os.environ.copy()

        if host_project_dir:
            log(f"Detected host project directory: {host_project_dir}", "INFO")
            env["COMPOSE_PROJECT_DIR"] = host_project_dir
        else:
            log(
                "HOST_PROJECT_DIR not set. Volume mounts for monitoring stack might fail or be empty.",
                "WARNING",
            )

        try:
            subprocess.run(
                ["docker", "compose", "--profile", "monitoring", "up", "-d"], env=env, check=True
            )
            log("Monitoring stack started", "SUCCESS")
        except (subprocess.CalledProcessError, FileNotFoundError):
            log("Failed to auto-start monitoring stack.", "WARNING")
            log(
                "You can start it manually by running: docker compose --profile monitoring up -d",
                "INFO",
            )

    print("")
    print("\033[0;32m╔══════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[0;32m║                    Bootstrap Complete!                       ║\033[0m")
    print("\033[0;32m╚══════════════════════════════════════════════════════════════╝\033[0m")
    print("")
    print("Service URLs:")
    print(f"  • Prowlarr:    {prowlarr_url} (Indexer management)")
    print(f"  • Sonarr:      {sonarr_url} (TV shows)")
    print(f"  • Radarr:      {radarr_url} (Movies)")
    print(f"  • Bazarr:      {bazarr_url} (Subtitles)")
    print(f"  • qBittorrent: {qbittorrent_url} (Downloads)")
    print("")
    print(f"Configuration saved to: {ENV_FILE}")
    print("")


if __name__ == "__main__":
    main()
