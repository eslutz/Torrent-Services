import os
import sys
import time
import requests
import json
import subprocess
import re
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load_env, log, QBitClient

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    log(
        "Playwright is not installed. Please run: pip install playwright && playwright install",
        "ERROR",
    )
    sys.exit(1)


def generate_gluetun_apikey():
    """Generate a secure random API key using gluetun's genkey command."""
    try:
        result = subprocess.check_output(
            ["docker", "run", "--rm", "qmcgaw/gluetun", "genkey"],
            stderr=subprocess.STDOUT
        )
        apikey = result.decode("utf-8").strip()
        log(f"Generated gluetun API key", "SUCCESS")
        return apikey
    except Exception as e:
        log(f"Failed to generate gluetun API key: {e}", "ERROR")
        return None


def setup_gluetun_control_server():
    """Setup gluetun control server authentication via .env."""
    log("Setting up Gluetun control server authentication...", "INFO")

    # Generate new API key
    apikey = generate_gluetun_apikey()
    if not apikey:
        log("Could not generate gluetun API key, skipping control server setup", "ERROR")
        return None

    return apikey


def update_env_apikey(apikey):
    """Update .env with CONTROL_APIKEY."""
    if not apikey:
        return

    env_path = Path(".env")
    if not env_path.exists():
        log(".env file not found", "ERROR")
        return

    try:
        with open(env_path, 'r') as f:
            content = f.read()

        # Check if key already exists
        if re.search(r'CONTROL_APIKEY\s*=', content):
            # Replace existing key
            content = re.sub(
                r'CONTROL_APIKEY\s*=.*',
                f'CONTROL_APIKEY="{apikey}"',
                content
            )
            log("Updated existing CONTROL_APIKEY in .env", "SUCCESS")
        else:
            # Add the key to .env
            if not content.endswith('\n'):
                content += '\n'
            content += f'CONTROL_APIKEY="{apikey}"\n'
            log("Added CONTROL_APIKEY to .env", "SUCCESS")

        with open(env_path, 'w') as f:
            f.write(content)

    except Exception as e:
        log(f"Failed to update .env with gluetun API key: {e}", "ERROR")



def get_qbittorrent_temp_password():
    try:
        # Run docker logs command
        result = subprocess.check_output(
            ["docker", "logs", "qbittorrent"], stderr=subprocess.STDOUT
        )
        logs = result.decode("utf-8")

        # Find the temporary password
        match = re.search(r"temporary password is provided for this session: ([A-Za-z0-9]+)", logs)
        if match:
            return match.group(1)
    except Exception as e:
        log(f"Failed to check docker logs: {e}", "WARNING")
    return None


def setup_qbittorrent_auth(url, target_user, target_pass):
    log("Checking qBittorrent authentication status...", "INFO")

    # 1. Try target credentials
    log("Checking if .env credentials are already configured...", "INFO")
    client = QBitClient(url, target_user, target_pass)
    if client.login():
        log("Authenticated with .env credentials", "SUCCESS")
        return

    # 2. Try temp password
    temp_pass = get_qbittorrent_temp_password()
    if temp_pass:
        log("Found temporary password in logs", "INFO")
        # Try logging in with admin/temp_pass
        temp_client = QBitClient(url, "admin", temp_pass)
        if temp_client.login():
            log("Authenticated with temporary password", "SUCCESS")

            # Update credentials
            log("Updating qBittorrent credentials to match .env...", "INFO")
            try:
                # Disable subnet whitelist
                temp_client.set_preferences({"bypass_auth_subnet_whitelist_enabled": False})

                payload = {"web_ui_username": target_user, "web_ui_password": target_pass}

                if temp_client.set_preferences(payload):
                    log("qBittorrent credentials updated successfully", "SUCCESS")
                else:
                    log("Failed to update qBittorrent credentials", "ERROR")
            except Exception as e:
                log(f"Error updating qBittorrent credentials: {e}", "ERROR")
            return
    else:
        log("No temporary password found in logs", "INFO")

    log("Could not authenticate with qBittorrent using any known credentials", "ERROR")


def setup_auth_for_service(page, name, url, username, password):
    log(f"Checking authentication for {name}...", "INFO")
    try:
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Selectors for login/setup inputs
        # *Arr apps and Bazarr generally use name="username" and name="password"
        username_selector = "input[name='username']"
        password_selector = "input[name='password']"

        # Fallback selectors if name attribute isn't used
        username_fallback = "input[placeholder='Username']"
        password_fallback = "input[placeholder='Password']"

        # Button selectors
        submit_selector = "button[type='submit'], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Save')"

        # Check if username field is visible
        if page.is_visible(username_selector) or page.is_visible(username_fallback):
            log(f"Found login/setup form for {name}", "INFO")

            # Fill username
            if page.is_visible(username_selector):
                page.fill(username_selector, username)
            else:
                page.fill(username_fallback, username)

            # Fill password
            if page.is_visible(password_selector):
                page.fill(password_selector, password)
            else:
                page.fill(password_fallback, password)

            # Check for confirm password (only likely in setup wizard)
            password_inputs = page.locator("input[type='password']")
            if password_inputs.count() > 1:
                # If there's a second password field, fill it too
                password_inputs.nth(1).fill(password)

            # Click submit
            if page.is_visible(submit_selector):
                page.click(submit_selector)

                # Wait for navigation
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                # Check if successful (form should be gone)
                if page.is_visible(username_selector) or page.is_visible(username_fallback):
                    log(
                        f"Still on login page for {name}. Authentication might have failed or was already set.",
                        "WARNING",
                    )
                else:
                    log(f"Successfully handled authentication for {name}", "SUCCESS")
            else:
                log(f"Could not find submit button for {name}", "ERROR")

        else:
            # No login form found.
            # Check if we are in the dashboard (e.g., check for common dashboard elements)
            # *Arr apps usually have a "System" or "Settings" link in the sidebar.
            if page.is_visible("a[href*='system']") or page.is_visible("a[href*='settings']"):
                log(f"No login form found for {name}. Dashboard is accessible.", "WARNING")
            else:
                log(f"No login form found for {name}, and dashboard not confirmed.", "WARNING")

    except Exception as e:
        log(f"Error setting up auth for {name}: {e}", "ERROR")


def main():
    load_env()

    username = os.environ.get("SERVICE_USER")

    if not username:
        log("SERVICE_USER not set in .env", "ERROR")
        sys.exit(1)

    # Gluetun Control Server Setup
    log("=" * 50, "INFO")
    log("Setting up Gluetun control server authentication", "INFO")
    log("=" * 50, "INFO")
    gluetun_apikey = setup_gluetun_control_server()
    if gluetun_apikey:
        update_env_apikey(gluetun_apikey)
    log("", "INFO")

    # qBittorrent Setup (Requests based)
    qbittorrent_url = os.environ.get("QBIT_URL", "http://localhost:8080")
    qbittorrent_pass = os.environ.get("QBITTORRENT_PASSWORD")
    if qbittorrent_pass:
        setup_qbittorrent_auth(qbittorrent_url, username, qbittorrent_pass)
    else:
        log("QBITTORRENT_PASSWORD not set. Skipping qBittorrent auth setup.", "WARNING")

    # *Arr + Bazarr Setup (Playwright based)
    # Define service configuration: (Name, URL_Env_Var, Default_URL, Password_Env_Var)
    service_configs = [
        ("Prowlarr", "PROWLARR_URL", "http://localhost:9696", "PROWLARR_PASSWORD"),
        ("Sonarr", "SONARR_URL", "http://localhost:8989", "SONARR_PASSWORD"),
        ("Radarr", "RADARR_URL", "http://localhost:7878", "RADARR_PASSWORD"),
        ("Bazarr", "BAZARR_URL", "http://localhost:6767", "BAZARR_PASSWORD"),
    ]

    with sync_playwright() as p:
        log("Launching browser...", "INFO")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for name, url_env, default_url, pass_env in service_configs:
            url = os.environ.get(url_env, default_url)
            password = os.environ.get(pass_env)

            if not password:
                log(f"No password found for {name}. Skipping.", "WARNING")
                continue
            setup_auth_for_service(page, name, url, username, password)

        browser.close()
        log("Authentication setup complete", "SUCCESS")


if __name__ == "__main__":
    main()
