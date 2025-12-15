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
    configure_config_endpoint,
    configure_root_folders,
)

load_env()

CONFIG = load_config()
RADARR_CONFIG = CONFIG.get("radarr", {})
RADARR_URL = os.environ.get("RADARR_URL", RADARR_CONFIG.get("url", "http://localhost:7878"))


def get_schema_for_client(implementation, api_key):
    headers = get_headers(api_key)
    schemas = requests.get(f"{RADARR_URL}/api/v3/downloadclient/schema", headers=headers).json()
    return next((s for s in schemas if s["implementation"] == implementation), None)


def configure_download_clients(api_key):
    log("Configuring Download Clients...", "INFO")
    headers = get_headers(api_key)
    clients = RADARR_CONFIG.get("download_clients", [])

    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/downloadclient", headers=headers)
        resp.raise_for_status()
        existing_clients = resp.json()
        existing_map = {c["name"]: c for c in existing_clients}

        for client_config in clients:
            name = client_config["name"]
            implementation = client_config["implementation"]

            schema = get_schema_for_client(implementation, api_key)
            if not schema:
                log(f"Schema not found for {implementation}, skipping", "WARNING")
                continue

            if name in existing_map:
                fields = existing_map[name]["fields"]
            else:
                fields = schema["fields"]

            if "fields" in client_config:
                for override in client_config["fields"]:
                    value = override.get("value")
                    if "env" in override:
                        env_val = os.environ.get(override["env"])
                        if env_val:
                            value = env_val
                        else:
                            log(
                                f"Environment variable {override['env']} not found for {name}",
                                "WARNING",
                            )

                    for field in fields:
                        if field["name"] == override["name"]:
                            field["value"] = value
                            break

            payload = {
                "name": name,
                "implementation": implementation,
                "protocol": client_config["protocol"],
                "configContract": schema["configContract"],
                "fields": fields,
                "enable": True,
                "priority": 1,
            }

            if name in existing_map:
                payload["id"] = existing_map[name]["id"]
                requests.put(
                    f"{RADARR_URL}/api/v3/downloadclient/{payload['id']}",
                    headers=headers,
                    json=payload,
                ).raise_for_status()
                log(f"Download client {name} updated", "SUCCESS")
            else:
                requests.post(
                    f"{RADARR_URL}/api/v3/downloadclient", headers=headers, json=payload
                ).raise_for_status()
                log(f"Download client {name} created", "SUCCESS")

    except Exception as e:
        log(f"Failed to configure download clients: {e}", "ERROR")


def main():
    log("Starting Radarr Setup...", "INFO")
    api_key = get_api_key("RADARR_API_KEY")
    wait_for_service(RADARR_URL, api_key, "Radarr")
    disable_analytics(RADARR_URL, api_key, "Radarr")

    configure_config_endpoint(
        RADARR_URL,
        api_key,
        "mediaManagement",
        RADARR_CONFIG.get("media_management"),
        "Media Management",
    )

    configure_config_endpoint(RADARR_URL, api_key, "naming", RADARR_CONFIG.get("naming"), "Naming")

    configure_root_folders(RADARR_URL, api_key, RADARR_CONFIG.get("root_folders", []))

    configure_download_clients(api_key)

    log("Radarr Setup Complete!", "SUCCESS")


if __name__ == "__main__":
    main()
