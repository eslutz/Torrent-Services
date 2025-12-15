import os
import requests
from common import (
    load_env,
    load_config,
    log,
    get_api_key,
    get_headers,
    wait_for_service,
    disable_analytics,
)

load_env()

CONFIG = load_config()
PROWLARR_CONFIG = CONFIG.get("prowlarr", {})
PROWLARR_URL = os.environ.get("PROWLARR_URL", PROWLARR_CONFIG.get("url", "http://localhost:9696"))


def get_tag_id(label, api_key):
    headers = get_headers(api_key)
    tags = requests.get(f"{PROWLARR_URL}/api/v1/tag", headers=headers).json()
    for tag in tags:
        if tag["label"] == label:
            return tag["id"]

    log(f"Creating tag: {label}", "INFO")
    resp = requests.post(f"{PROWLARR_URL}/api/v1/tag", headers=headers, json={"label": label})
    resp.raise_for_status()
    return resp.json()["id"]


def configure_proxy(api_key):
    log("Configuring Tor Proxy...", "INFO")
    headers = get_headers(api_key)

    # Get tag ID
    tag_id = get_tag_id("tor-proxy", api_key)

    # Check existing proxies
    proxies = requests.get(f"{PROWLARR_URL}/api/v1/indexerproxy", headers=headers).json()
    existing = next((p for p in proxies if p["name"] == "Tor"), None)

    payload = {
        "name": "Tor",
        "implementationName": "Socks5",
        "implementation": "Socks5",
        "configContract": "Socks5Settings",
        "fields": [
            {"name": "host", "value": "torarr"},
            {"name": "port", "value": 9050},
            {"name": "username", "value": ""},
            {"name": "password", "value": ""},
        ],
        "tags": [tag_id],
    }

    if existing:
        payload["id"] = existing["id"]
        requests.put(
            f"{PROWLARR_URL}/api/v1/indexerproxy/{existing['id']}", headers=headers, json=payload
        ).raise_for_status()
        log("Tor Proxy updated", "SUCCESS")
    else:
        requests.post(
            f"{PROWLARR_URL}/api/v1/indexerproxy", headers=headers, json=payload
        ).raise_for_status()
        log("Tor Proxy created", "SUCCESS")


def get_schema_for_indexer(name, api_key):
    headers = get_headers(api_key)
    schemas = requests.get(f"{PROWLARR_URL}/api/v1/indexer/schema", headers=headers).json()
    return next((s for s in schemas if s["name"] == name), None)


def configure_indexers(api_key):
    log("Configuring Indexers...", "INFO")
    headers = get_headers(api_key)

    existing_indexers = requests.get(f"{PROWLARR_URL}/api/v1/indexer", headers=headers).json()
    existing_map = {i["name"]: i for i in existing_indexers}

    for idx_config in PROWLARR_CONFIG.get("indexers", []):
        name = idx_config["name"]
        log(f"Processing indexer: {name}", "INFO")

        schema = get_schema_for_indexer(name, api_key)
        if not schema:
            log(f"Schema not found for {name}, skipping", "WARNING")
            continue

        if name in existing_map:
            fields = existing_map[name]["fields"]
        else:
            fields = schema["fields"]

        if "fields" in idx_config:
            for override in idx_config["fields"]:
                for field in fields:
                    if field["name"] == override["name"]:
                        field["value"] = override["value"]

        if "secrets" in idx_config:
            for secret in idx_config["secrets"]:
                env_val = os.environ.get(secret["env"])
                if env_val:
                    for field in fields:
                        if field["name"] == secret["field"]:
                            field["value"] = env_val
                else:
                    log(f"Secret env var {secret['env']} not found for {name}", "WARNING")

        tag_ids = []
        if "tags" in idx_config:
            for tag_label in idx_config["tags"]:
                tag_ids.append(get_tag_id(tag_label, api_key))

        payload = {
            "name": name,
            "implementation": schema["implementation"],
            "implementationName": schema["implementationName"],
            "configContract": schema["configContract"],
            "fields": fields,
            "enable": True,
            "protocol": schema["protocol"],
            "priority": idx_config.get("priority", 25),
            "tags": tag_ids,
            "appProfileId": 1,
        }

        if name in existing_map:
            payload["id"] = existing_map[name]["id"]
            try:
                requests.put(
                    f"{PROWLARR_URL}/api/v1/indexer/{payload['id']}", headers=headers, json=payload
                ).raise_for_status()
                log(f"Indexer {name} updated", "SUCCESS")
            except Exception as e:
                error_msg = e.response.text if hasattr(e, "response") and e.response else str(e)
                log(f"Failed to update {name}: {error_msg}", "ERROR")
        else:
            try:
                requests.post(
                    f"{PROWLARR_URL}/api/v1/indexer", headers=headers, json=payload
                ).raise_for_status()
                log(f"Indexer {name} created", "SUCCESS")
            except Exception as e:
                error_msg = e.response.text if hasattr(e, "response") and e.response else str(e)
                log(f"Failed to create {name}: {error_msg}", "ERROR")


def configure_apps(api_key):
    log("Configuring Applications...", "INFO")
    headers = get_headers(api_key)

    sonarr_key = os.environ.get("SONARR_API_KEY")
    radarr_key = os.environ.get("RADARR_API_KEY")

    apps = requests.get(f"{PROWLARR_URL}/api/v1/applications", headers=headers).json()
    app_map = {a["name"]: a for a in apps}

    # Sonarr
    if sonarr_key:
        payload = {
            "name": "Sonarr",
            "syncLevel": "fullSync",
            "implementation": "Sonarr",
            "configContract": "SonarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://sonarr:8989"},
                {"name": "apiKey", "value": sonarr_key},
                {"name": "syncCategories", "value": [5000, 5010, 5020, 5030, 5040, 5045, 5050]},
            ],
            "tags": [],
        }
        if "Sonarr" in app_map:
            payload["id"] = app_map["Sonarr"]["id"]
            requests.put(
                f"{PROWLARR_URL}/api/v1/applications/{payload['id']}", headers=headers, json=payload
            )
            log("Sonarr app updated", "SUCCESS")
        else:
            requests.post(f"{PROWLARR_URL}/api/v1/applications", headers=headers, json=payload)
            log("Sonarr app created", "SUCCESS")

    # Radarr
    if radarr_key:
        payload = {
            "name": "Radarr",
            "syncLevel": "fullSync",
            "implementation": "Radarr",
            "configContract": "RadarrSettings",
            "fields": [
                {"name": "prowlarrUrl", "value": "http://prowlarr:9696"},
                {"name": "baseUrl", "value": "http://radarr:7878"},
                {"name": "apiKey", "value": radarr_key},
                {
                    "name": "syncCategories",
                    "value": [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060],
                },
            ],
            "tags": [],
        }
        if "Radarr" in app_map:
            payload["id"] = app_map["Radarr"]["id"]
            requests.put(
                f"{PROWLARR_URL}/api/v1/applications/{payload['id']}", headers=headers, json=payload
            )
            log("Radarr app updated", "SUCCESS")
        else:
            requests.post(f"{PROWLARR_URL}/api/v1/applications", headers=headers, json=payload)
            log("Radarr app created", "SUCCESS")


def main():
    api_key = get_api_key("PROWLARR_API_KEY")
    wait_for_service(PROWLARR_URL, api_key, "Prowlarr", endpoint="/api/v1/system/status")
    disable_analytics(PROWLARR_URL, api_key, "Prowlarr", api_version="v1")
    configure_proxy(api_key)
    configure_indexers(api_key)
    configure_apps(api_key)


if __name__ == "__main__":
    main()
