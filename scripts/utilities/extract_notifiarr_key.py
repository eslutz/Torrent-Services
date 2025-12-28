#!/usr/bin/env python3
"""
Extract Notifiarr API key from container logs or config file.

This script helps retrieve the Notifiarr API key when it's been configured
but not saved to .env. It checks both the container logs and config file.
"""

import re
import sys
import json
import subprocess
from pathlib import Path


def log(msg, level="INFO"):
    """Print colored log messages."""
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
    }
    end = "\033[0m"
    print(f"{colors.get(level, '')}[{level}] {msg}{end}")


def extract_from_config():
    """Extract API key from Notifiarr config file."""
    config_path = Path("config/notifiarr/notifiarr.conf")

    if not config_path.exists():
        log(f"Config file not found: {config_path}", "WARNING")
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # Notifiarr stores the API key in the 'apikey' field
        api_key = config.get("apikey", "")

        if api_key:
            log("Found API key in config file", "SUCCESS")
            return api_key
        else:
            log("No API key found in config file", "WARNING")
            return None

    except json.JSONDecodeError as e:
        log(f"Failed to parse config file as JSON: {e}", "ERROR")
        return None
    except Exception as e:
        log(f"Error reading config file: {e}", "ERROR")
        return None


def extract_from_logs():
    """Extract API key from Notifiarr container logs."""
    try:
        # Get container logs
        result = subprocess.run(
            ["docker", "logs", "notifiarr", "--tail", "500"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            log("Failed to get container logs", "WARNING")
            return None

        logs = result.stdout + result.stderr

        # Look for API key patterns in logs
        # Notifiarr may log the API key during startup or in error messages
        for line in logs.split("\n"):
            # Common patterns where API key might appear
            if "api" in line.lower() and "key" in line.lower():
                # Notifiarr API keys are long alphanumeric strings (typically 40+ chars)
                # Match sequences that look like API keys with specific length
                matches = re.findall(r'\b[a-zA-Z0-9]{40,64}\b', line)
                if matches:
                    # Additional validation: keys shouldn't contain common words
                    for match in matches:
                        if not any(word in match.lower() for word in ['http', 'https', 'docker']):
                            log(f"Possible API key found in logs: {match[:8]}...", "INFO")
                            return match

        log("No API key found in recent logs", "WARNING")
        return None

    except subprocess.TimeoutExpired:
        log("Timeout while reading container logs", "ERROR")
        return None
    except Exception as e:
        log(f"Error reading logs: {e}", "ERROR")
        return None


def extract_from_env():
    """Check if API key is already in container environment."""
    try:
        result = subprocess.run(
            ["docker", "exec", "notifiarr", "printenv", "DN_API_KEY"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            api_key = result.stdout.strip()
            log("Found API key in container environment", "SUCCESS")
            return api_key

        return None

    except Exception as e:
        log(f"Could not check container environment: {e}", "WARNING")
        return None


def update_env_file(api_key):
    """Update .env file with the extracted API key."""
    env_path = Path(".env")

    if not env_path.exists():
        log(".env file not found", "ERROR")
        return False

    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        # Check if NOTIFIARR_API_KEY already exists
        key_exists = False
        updated_lines = []

        for line in lines:
            if line.strip().startswith("NOTIFIARR_API_KEY="):
                key_exists = True
                # Update the existing line
                updated_lines.append(f'NOTIFIARR_API_KEY="{api_key}"\n')
                log("Updated existing NOTIFIARR_API_KEY in .env", "SUCCESS")
            else:
                updated_lines.append(line)

        if not key_exists:
            # Add the key at the end, checking for trailing newline
            if updated_lines and not updated_lines[-1].endswith('\n'):
                updated_lines.append('\n')
            updated_lines.append(f'NOTIFIARR_API_KEY="{api_key}"\n')
            log("Added NOTIFIARR_API_KEY to .env", "SUCCESS")

        # Write back to file
        with open(env_path, "w") as f:
            f.writelines(updated_lines)

        return True

    except Exception as e:
        log(f"Error updating .env file: {e}", "ERROR")
        return False


def main():
    """Main function to extract and save Notifiarr API key."""
    log("Extracting Notifiarr API key...", "INFO")
    print()

    # Try different extraction methods in order of reliability
    api_key = None

    # 1. Try config file (most reliable)
    log("Checking config file...", "INFO")
    api_key = extract_from_config()

    # 2. Try container environment
    if not api_key:
        log("Checking container environment...", "INFO")
        api_key = extract_from_env()

    # 3. Try logs (least reliable)
    if not api_key:
        log("Checking container logs...", "INFO")
        api_key = extract_from_logs()

    print()

    if not api_key:
        log("Could not extract Notifiarr API key from any source", "ERROR")
        log("Please configure the API key manually:", "INFO")
        log("  1. Sign up at https://notifiarr.com", "INFO")
        log("  2. Get your API key from the dashboard", "INFO")
        log("  3. Add to .env: NOTIFIARR_API_KEY=your_key_here", "INFO")
        return 1

    # Display the key
    log(f"Extracted API key: {api_key[:8]}...{api_key[-4:]}", "SUCCESS")
    print()

    # Ask user if they want to save it to .env
    try:
        response = input("Save this API key to .env file? (yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            if update_env_file(api_key):
                log("API key saved to .env successfully", "SUCCESS")
                log("Restart Notifiarr container to apply changes:", "INFO")
                log("  docker compose restart notifiarr", "INFO")
                return 0
            else:
                return 1
        else:
            log("Skipped saving to .env", "INFO")
            log("Manual command to add to .env:", "INFO")
            log(f'  echo \'NOTIFIARR_API_KEY="{api_key}"\' >> .env', "INFO")
            return 0
    except KeyboardInterrupt:
        print()
        log("Cancelled by user", "WARNING")
        return 1


if __name__ == "__main__":
    sys.exit(main())
