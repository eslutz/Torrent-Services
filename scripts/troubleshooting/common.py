import os
import json
import requests
import sys

class Config:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.abspath(os.path.join(self.script_dir, "../../"))
        self.env_path = os.path.join(self.root_dir, ".env")
        self.config_path = os.path.join(self.script_dir, "troubleshooting.config.json")
        
        self.env = self._load_env()
        self.settings = self._load_config()
        
        self.qbit_user = self.env.get("SERVICE_USER", "admin")
        self.qbit_pass = self.env.get("QBITTORRENT_PASSWORD")
        self.base_url = self.settings.get("qbittorrent_url", "http://localhost:8080")
        
        _bt_backup = self.settings.get("bt_backup_path")
        self.bt_backup_path = os.path.expanduser(_bt_backup) if _bt_backup else None
        
        self.default_save_path = self.settings.get("default_save_path")
        
        _scan_path = self.settings.get("default_scan_path")
        self.default_scan_path = os.path.expanduser(_scan_path) if _scan_path else None

    def _load_env(self):
        env_vars = {}
        if os.path.exists(self.env_path):
            with open(self.env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        # Remove quotes if present
                        value = value.strip()
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        env_vars[key.strip()] = value
        return env_vars

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return {}

class QBitClient:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.logged_in = False

    def login(self):
        if self.logged_in:
            return True
            
        url = f"{self.config.base_url}/api/v2/auth/login"
        data = {"username": self.config.qbit_user, "password": self.config.qbit_pass}
        try:
            response = self.session.post(url, data=data)
            response.raise_for_status()
            if response.text == "Ok.":
                self.logged_in = True
                return True
        except Exception as e:
            print(f"Login error: {e}")
        return False

    def get_torrents(self, hashes=None):
        if not self.login(): return []
        url = f"{self.config.base_url}/api/v2/torrents/info"
        params = {}
        if hashes:
            params["hashes"] = hashes
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting torrents: {e}")
            return []

    def get_trackers(self, hash_val):
        if not self.login(): return []
        url = f"{self.config.base_url}/api/v2/torrents/trackers"
        params = {"hash": hash_val}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return []

    def pause_torrent(self, hashes):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/pause"
        self.session.post(url, data={"hashes": hashes})

    def resume_torrent(self, hashes):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/resume"
        self.session.post(url, data={"hashes": hashes})

    def recheck_torrent(self, hashes):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/recheck"
        self.session.post(url, data={"hashes": hashes})

    def reannounce_torrent(self, hashes):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/reannounce"
        self.session.post(url, data={"hashes": hashes})

    def set_location(self, hashes, location):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/setLocation"
        self.session.post(url, data={"hashes": hashes, "location": location})

    def delete_torrents(self, hashes, delete_files=False):
        if not self.login(): return
        url = f"{self.config.base_url}/api/v2/torrents/delete"
        data = {
            "hashes": hashes,
            "deleteFiles": "true" if delete_files else "false"
        }
        self.session.post(url, data=data)

    def add_torrent_file(self, file_path, save_path=None):
        if not self.login(): return False
        url = f"{self.config.base_url}/api/v2/torrents/add"
        files = {'torrents': open(file_path, 'rb')}
        data = {}
        if save_path:
            data['savepath'] = save_path
        try:
            self.session.post(url, files=files, data=data)
            return True
        except Exception as e:
            print(f"Error adding torrent: {e}")
            return False

    def get_preferences(self):
        if not self.login(): return {}
        url = f"{self.config.base_url}/api/v2/app/preferences"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting preferences: {e}")
            return {}
