import os
import sys
import time
import requests
import json
import subprocess
import re
from common import load_env, log

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    log(
        "Playwright is not installed. Please run: pip install playwright && playwright install",
        "ERROR",
    )
    sys.exit(1)


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


def qbit_login(url, username, password):
    try:
        session = requests.Session()
        resp = session.post(
            f"{url}/api/v2/auth/login", data={"username": username, "password": password}
        )

        if resp.status_code == 200 and resp.text != "Fails.":
            # Verify login by checking version
            try:
                v_resp = session.get(f"{url}/api/v2/app/version")
                if v_resp.status_code == 200:
                    return session
            except:
                pass
    except Exception as e:
        pass
    return None


def setup_qbittorrent_auth(url, target_user, target_pass):
    log("Checking qBittorrent authentication status...", "INFO")

    # 1. Try target credentials
    log("Checking if .env credentials are already configured...", "INFO")
    session = qbit_login(url, target_user, target_pass)
    if session:
        log("Authenticated with .env credentials", "SUCCESS")
        return

    # 2. Try temp password
    temp_pass = get_qbittorrent_temp_password()
    if temp_pass:
        log(f"Found temporary password: {temp_pass}", "INFO")
        session = qbit_login(url, "admin", temp_pass)
        if session:
            log("Authenticated with temporary password", "SUCCESS")

            # Update credentials
            log("Updating qBittorrent credentials to match .env...", "INFO")
            try:
                # Disable subnet whitelist to ensure we can access
                session.post(
                    f"{url}/api/v2/app/setPreferences",
                    data={"json": json.dumps({"bypass_auth_subnet_whitelist_enabled": False})},
                )

                payload = {"web_ui_username": target_user, "web_ui_password": target_pass}

                resp = session.post(
                    f"{url}/api/v2/app/setPreferences", data={"json": json.dumps(payload)}
                )

                if resp.status_code == 200:
                    log("qBittorrent credentials updated successfully", "SUCCESS")
                else:
                    log(
                        f"Failed to update qBittorrent credentials: {resp.status_code} {resp.text}",
                        "ERROR",
                    )
            except Exception as e:
                log(f"Error updating qBittorrent credentials: {e}", "ERROR")
            return
    else:
        log("No temporary password found in logs", "INFO")

    log("Could not authenticate with qBittorrent using any known credentials", "ERROR")


def setup_auth_for_service(page, name, url, username, password):
    log(f"Checking authentication for {name} at {url}...", "INFO")
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

    # qBittorrent Setup (Requests based)
    qbit_url = os.environ.get("QBIT_URL", "http://localhost:8080")
    qbit_pass = os.environ.get("QBITTORRENT_PASSWORD")
    if qbit_pass:
        setup_qbittorrent_auth(qbit_url, username, qbit_pass)
    else:
        log("QBITTORRENT_PASSWORD not set. Skipping qBittorrent auth setup.", "WARNING")

    # *Arr + Bazarr Setup (Playwright based)
    services = [
        (
            "Prowlarr",
            os.environ.get("PROWLARR_URL", "http://localhost:9696"),
            os.environ.get("PROWLARR_PASSWORD"),
        ),
        (
            "Sonarr",
            os.environ.get("SONARR_URL", "http://localhost:8989"),
            os.environ.get("SONARR_PASSWORD"),
        ),
        (
            "Radarr",
            os.environ.get("RADARR_URL", "http://localhost:7878"),
            os.environ.get("RADARR_PASSWORD"),
        ),
        (
            "Bazarr",
            os.environ.get("BAZARR_URL", "http://localhost:6767"),
            os.environ.get("BAZARR_PASSWORD"),
        ),
    ]

    with sync_playwright() as p:
        log("Launching browser...", "INFO")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for name, url, password in services:
            if not password:
                log(f"No password found for {name}. Skipping.", "WARNING")
                continue
            setup_auth_for_service(page, name, url, username, password)

        browser.close()
        log("Authentication setup complete", "SUCCESS")


if __name__ == "__main__":
    main()
