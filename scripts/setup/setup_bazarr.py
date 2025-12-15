import os
import requests
from common import load_env, load_config, log, get_api_key, get_headers

load_env()

CONFIG = load_config()
BAZARR_CONFIG = CONFIG.get("bazarr", {})
BAZARR_URL = os.environ.get("BAZARR_URL", BAZARR_CONFIG.get("url", "http://localhost:6767"))


def wait_for_bazarr(api_key):
    log("Waiting for Bazarr API...", "INFO")
    headers = get_headers(api_key, "X-API-KEY")
    import time

    for _ in range(30):
        try:
            requests.get(f"{BAZARR_URL}/api/system/status", headers=headers)
            log("Bazarr API is ready", "SUCCESS")
            return
        except:
            time.sleep(2)
    log("Bazarr not reachable", "ERROR")
    import sys

    sys.exit(1)


def configure_sonarr(bazarr_api_key, sonarr_api_key):
    log("Configuring Bazarr -> Sonarr...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")

    sonarr_config = BAZARR_CONFIG.get("sonarr", {})
    if not sonarr_config:
        log("No Sonarr configuration found in setup.config.json", "WARNING")
        return

    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/settings", headers=headers)
        resp.raise_for_status()
        current_settings = resp.json()

        use_sonarr = current_settings.get("general", {}).get("use_sonarr", False)
        current_sonarr_apikey = current_settings.get("sonarr", {}).get("apikey", "")

        if use_sonarr and current_sonarr_apikey == sonarr_api_key:
            log("Bazarr -> Sonarr already configured", "SUCCESS")
            return
    except Exception as e:
        log(f"Failed to check current settings: {e}", "WARNING")

    # Build payload from config
    payload = {
        "sonarr": {
            "ip": sonarr_config.get("ip", "sonarr"),
            "port": sonarr_config.get("port", 8989),
            "base_url": sonarr_config.get("base_url", ""),
            "ssl": sonarr_config.get("ssl", False),
            "apikey": sonarr_api_key,
            "full_update": sonarr_config.get("full_update", "Daily"),
            "full_update_day": sonarr_config.get("full_update_day", 6),
            "full_update_hour": sonarr_config.get("full_update_hour", 4),
            "only_monitored": sonarr_config.get("only_monitored", True),
            "series_sync": sonarr_config.get("series_sync", 60),
            "excluded_tags": sonarr_config.get("excluded_tags", []),
            "excluded_series_types": sonarr_config.get("excluded_series_types", []),
        },
        "general": {"use_sonarr": True},
    }

    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr -> Sonarr configured", "SUCCESS")
    except Exception as e:
        import sys

        log(f"Failed to configure Bazarr -> Sonarr: {e}", "ERROR")
        sys.exit(1)


def configure_radarr(bazarr_api_key, radarr_api_key):
    log("Configuring Bazarr -> Radarr...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")

    radarr_config = BAZARR_CONFIG.get("radarr", {})
    if not radarr_config:
        log("No Radarr configuration found in setup.config.json", "WARNING")
        return

    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/settings", headers=headers)
        resp.raise_for_status()
        current_settings = resp.json()

        use_radarr = current_settings.get("general", {}).get("use_radarr", False)
        current_radarr_apikey = current_settings.get("radarr", {}).get("apikey", "")

        if use_radarr and current_radarr_apikey == radarr_api_key:
            log("Bazarr -> Radarr already configured", "SUCCESS")
            return
    except Exception as e:
        log(f"Failed to check current settings: {e}", "WARNING")

    # Build payload from config
    payload = {
        "radarr": {
            "ip": radarr_config.get("ip", "radarr"),
            "port": radarr_config.get("port", 7878),
            "base_url": radarr_config.get("base_url", ""),
            "ssl": radarr_config.get("ssl", False),
            "apikey": radarr_api_key,
            "full_update": radarr_config.get("full_update", "Daily"),
            "full_update_day": radarr_config.get("full_update_day", 6),
            "full_update_hour": radarr_config.get("full_update_hour", 4),
            "only_monitored": radarr_config.get("only_monitored", True),
            "movies_sync": radarr_config.get("movies_sync", 60),
            "excluded_tags": radarr_config.get("excluded_tags", []),
        },
        "general": {"use_radarr": True},
    }

    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr -> Radarr configured", "SUCCESS")
    except Exception as e:
        import sys

        log(f"Failed to configure Bazarr -> Radarr: {e}", "ERROR")
        sys.exit(1)


def configure_general_settings(bazarr_api_key):
    log("Configuring Bazarr general settings...", "INFO")
    headers = get_headers(bazarr_api_key, "X-API-KEY")
    general_config = BAZARR_CONFIG.get("general", {})

    if not general_config:
        return

    payload = {"general": {}}

    # Map all general settings from config
    for key, value in general_config.items():
        payload["general"][key] = value

    if not payload["general"]:
        return

    try:
        resp = requests.post(f"{BAZARR_URL}/api/system/settings", headers=headers, json=payload)
        resp.raise_for_status()
        log("Bazarr general settings configured", "SUCCESS")
    except Exception as e:
        log(f"Failed to configure Bazarr general settings: {e}", "ERROR")


def configure_language_profiles(api_key):
    log("Configuring language profiles...", "INFO")
    headers = get_headers(api_key, "X-API-KEY")
    profiles_config = BAZARR_CONFIG.get("language_profiles", [])

    if not profiles_config:
        log("No language profiles configured", "INFO")
        return

    try:
        resp = requests.get(f"{BAZARR_URL}/api/system/languages-profiles", headers=headers)
        resp.raise_for_status()
        existing_profiles = resp.json()

        for profile_config in profiles_config:
            profile_name = profile_config["name"]
            existing_profile = next(
                (p for p in existing_profiles if p.get("name") == profile_name), None
            )

            payload = {"name": profile_name, "items": []}

            for lang in profile_config.get("languages", []):
                payload["items"].append(
                    {
                        "language": lang["language"],
                        "forced": "True" if lang.get("forced", False) else "False",
                        "hi": "True" if lang.get("hi", False) else "False",
                        "audio_exclude": lang.get("audio_exclude", "False"),
                    }
                )

            if existing_profile:
                profile_id = existing_profile.get("profileId")
                payload["profileId"] = profile_id

                # Check if update is needed (simple comparison)
                # Note: This might need more robust comparison logic
                log(f"Updating language profile: {profile_name}", "INFO")
                resp = requests.post(
                    f"{BAZARR_URL}/api/system/languages-profiles", headers=headers, json=payload
                )
                resp.raise_for_status()
                log(f"Language profile '{profile_name}' updated", "SUCCESS")
            else:
                log(f"Creating language profile: {profile_name}", "INFO")
                resp = requests.put(
                    f"{BAZARR_URL}/api/system/languages-profiles", headers=headers, json=payload
                )
                resp.raise_for_status()
                log(f"Language profile '{profile_name}' created", "SUCCESS")

    except Exception as e:
        log(f"Failed to configure language profiles: {e}", "ERROR")


def configure_providers(api_key):
    log("Configuring subtitle providers...", "INFO")
    headers = get_headers(api_key, "X-API-KEY")

    # Get enabled providers list from config
    enabled_providers = BAZARR_CONFIG.get("general", {}).get("enabled_providers", [])
    if not enabled_providers:
        log("No providers enabled in config", "INFO")
        return

    # Define provider configurations
    # Map provider name to (env_user_var, env_pass_var)
    provider_credentials = {
        "opensubtitlescom": ("SERVICE_USER", "OPENSUBTITLESCOM_PASS"),
        "addic7ed": ("SERVICE_USER", "ADDIC7ED_PASS"),
        "podnapisi": (None, None),  # No auth required usually
    }

    try:
        # Get existing providers to find IDs if we need to update
        resp = requests.get(f"{BAZARR_URL}/api/providers", headers=headers)
        resp.raise_for_status()
        existing_providers = {p["name"]: p for p in resp.json()}

        for provider_name in enabled_providers:
            if provider_name not in provider_credentials:
                log(f"Skipping unknown provider: {provider_name}", "WARNING")
                continue

            user_var, pass_var = provider_credentials[provider_name]
            username = os.environ.get(user_var) if user_var else ""
            password = os.environ.get(pass_var) if pass_var else ""

            # Skip if credentials required but missing
            if user_var and (not username or not password):
                log(f"Skipping {provider_name}: Missing credentials in .env", "WARNING")
                continue

            payload = {
                "enabled": True,
                "name": provider_name,
                # Common fields, some might be ignored by specific providers
                "username": username,
                "password": password,
                "use_tag_search": True,
            }

            if provider_name == "addic7ed":
                payload["cookies"] = os.environ.get("ADDIC7ED_COOKIES", "")
                payload["user_agent"] = os.environ.get("ADDIC7ED_USER_AGENT", "")

            if provider_name in existing_providers:
                # Update existing
                provider_id = existing_providers[provider_name]["id"]
                # Merge with existing to keep other settings? Or overwrite?
                # Usually safer to just update what we know.
                # But the API might require all fields.
                # Let's try a minimal update or just overwrite.
                # Bazarr API usually expects the full object or at least the changed fields.
                log(f"Updating provider: {provider_name}", "INFO")
                # We need to use the specific endpoint for the provider or the general one?
                # Bazarr API is a bit inconsistent. Let's try PUT /api/providers/{id}
                resp = requests.put(
                    f"{BAZARR_URL}/api/providers/{provider_id}", headers=headers, json=payload
                )
                if resp.status_code == 204 or resp.status_code == 200:
                    log(f"Provider '{provider_name}' updated", "SUCCESS")
                else:
                    log(f"Failed to update '{provider_name}': {resp.text}", "ERROR")
            else:
                # Create new - Bazarr might not support creating arbitrary providers via API
                # if they are not "known" types. But usually /api/providers lists available ones too?
                # Actually, usually you enable them from the available list.
                # If it's not in existing_providers (which lists configured ones),
                # we might need to find it in "available" providers?
                # For now, let's assume we can just POST to create/enable it.
                log(f"Enabling provider: {provider_name}", "INFO")
                # Note: Endpoint for creating might vary. Trying POST /api/providers
                resp = requests.post(f"{BAZARR_URL}/api/providers", headers=headers, json=payload)
                if resp.status_code == 201 or resp.status_code == 200:
                    log(f"Provider '{provider_name}' enabled", "SUCCESS")
                else:
                    log(f"Failed to enable '{provider_name}': {resp.text}", "ERROR")

    except Exception as e:
        log(f"Failed to configure providers: {e}", "ERROR")


def main():
    log("Starting Bazarr setup...", "INFO")

    bazarr_api_key = get_api_key("BAZARR_API_KEY")
    sonarr_api_key = get_api_key("SONARR_API_KEY")
    radarr_api_key = get_api_key("RADARR_API_KEY")

    wait_for_bazarr(bazarr_api_key)

    configure_sonarr(bazarr_api_key, sonarr_api_key)
    configure_radarr(bazarr_api_key, radarr_api_key)
    configure_general_settings(bazarr_api_key)
    configure_language_profiles(bazarr_api_key)
    configure_providers(bazarr_api_key)

    log("Bazarr setup completed successfully", "SUCCESS")


if __name__ == "__main__":
    main()
