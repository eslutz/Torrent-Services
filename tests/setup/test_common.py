import os
import sys
import pytest
import responses
from unittest.mock import patch

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))

from common import (
    load_config,
    log,
    get_api_key,
    get_headers,
    wait_for_service,
    disable_analytics,
    configure_root_folders,
    configure_download_clients,
)


class TestLoadConfig:
    def test_load_config_success(self, tmp_path):
        """Test loading configuration from JSON file"""
        config_file = tmp_path / "setup.config.json"
        config_file.write_text('{"prowlarr": {"url": "http://localhost:9696"}}')
        config = load_config(config_path=str(config_file))
        assert config["prowlarr"]["url"] == "http://localhost:9696"

    def test_load_config_missing_file(self, capsys):
        """Test loading from non-existent config file"""
        with pytest.raises(SystemExit):
            load_config(config_path="/nonexistent/config.json")


class TestLog:
    def test_log_info(self, capsys):
        """Test INFO level logging"""
        log("Test message", "INFO")
        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "Test message" in captured.out

    def test_log_success(self, capsys):
        """Test SUCCESS level logging"""
        log("Test success", "SUCCESS")
        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out
        assert "Test success" in captured.out

    def test_log_error(self, capsys):
        """Test ERROR level logging"""
        log("Test error", "ERROR")
        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Test error" in captured.out


class TestGetApiKey:
    def test_get_api_key_success(self):
        """Test retrieving API key from environment"""
        os.environ["TEST_API_KEY"] = "test123"
        api_key = get_api_key("TEST_API_KEY")
        assert api_key == "test123"

    def test_get_api_key_missing(self):
        """Test retrieving non-existent API key"""
        with pytest.raises(SystemExit):
            get_api_key("NONEXISTENT_KEY")


class TestGetHeaders:
    def test_get_headers_default(self):
        """Test getting headers with default header name"""
        headers = get_headers("test_api_key")
        assert headers["X-Api-Key"] == "test_api_key"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_custom(self):
        """Test getting headers with custom header name"""
        headers = get_headers("test_api_key", "Custom-Header")
        assert headers["Custom-Header"] == "test_api_key"
        assert headers["Content-Type"] == "application/json"


class TestWaitForService:
    @responses.activate
    def test_wait_for_service_success(self):
        """Test waiting for service that becomes ready"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/system/status",
            json={"status": "ok"},
            status=200,
        )

        result = wait_for_service("http://localhost:8989", "test_key", "Sonarr", max_retries=1)
        assert result is True

    @responses.activate
    def test_wait_for_service_timeout(self):
        """Test waiting for service that never becomes ready"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/system/status",
            body=Exception("Connection error"),
        )

        with pytest.raises(SystemExit):
            wait_for_service("http://localhost:8989", "test_key", "Sonarr", max_retries=1)


class TestDisableAnalytics:
    @responses.activate
    def test_disable_analytics_already_disabled(self):
        """Test disabling analytics when already disabled"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/config/host",
            json={"analyticsEnabled": False},
            status=200,
        )

        disable_analytics("http://localhost:8989", "test_key", "Sonarr")
        assert len(responses.calls) == 1

    @responses.activate
    def test_disable_analytics_enabled(self):
        """Test disabling analytics when enabled"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/config/host",
            json={"analyticsEnabled": True, "id": 1},
            status=200,
        )
        responses.add(
            responses.PUT,
            "http://localhost:8989/api/v3/config/host",
            json={"analyticsEnabled": False, "id": 1},
            status=200,
        )

        disable_analytics("http://localhost:8989", "test_key", "Sonarr")
        assert len(responses.calls) == 2


class TestConfigureRootFolders:
    @responses.activate
    def test_configure_root_folders_new(self):
        """Test adding a new root folder"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/rootfolder",
            json=[],
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8989/api/v3/rootfolder",
            json={"path": "/data/tv", "id": 1},
            status=201,
        )

        configure_root_folders("http://localhost:8989", "test_key", [{"path": "/data/tv"}])
        assert len(responses.calls) == 2

    @responses.activate
    def test_configure_root_folders_existing(self):
        """Test skipping existing root folder"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/rootfolder",
            json=[{"path": "/data/tv", "id": 1}],
            status=200,
        )

        configure_root_folders("http://localhost:8989", "test_key", [{"path": "/data/tv"}])
        assert len(responses.calls) == 1


class TestConfigureDownloadClients:
    @responses.activate
    def test_configure_download_clients_new(self):
        """Test adding a new download client"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/downloadclient",
            json=[],
            status=200,
        )
        responses.add(
            responses.POST,
            "http://localhost:8989/api/v3/downloadclient",
            json={"name": "qBittorrent", "id": 1},
            status=201,
        )

        client_config = [
            {
                "name": "qBittorrent",
                "protocol": "torrent",
                "implementation": "QBittorrent",
                "fields": [{"name": "host", "value": "localhost"}],
            }
        ]

        configure_download_clients("http://localhost:8989", "test_key", client_config)
        assert len(responses.calls) == 2

    @responses.activate
    def test_configure_download_clients_update(self):
        """Test updating existing download client"""
        responses.add(
            responses.GET,
            "http://localhost:8989/api/v3/downloadclient",
            json=[{"name": "qBittorrent", "id": 1}],
            status=200,
        )
        responses.add(
            responses.PUT,
            "http://localhost:8989/api/v3/downloadclient/1",
            json={"name": "qBittorrent", "id": 1},
            status=200,
        )

        client_config = [
            {
                "name": "qBittorrent",
                "protocol": "torrent",
                "implementation": "QBittorrent",
                "fields": [{"name": "host", "value": "localhost"}],
            }
        ]

        configure_download_clients("http://localhost:8989", "test_key", client_config)
        assert len(responses.calls) == 2

class TestQBitClient:
    """Test QBitClient methods"""
    
    @responses.activate
    def test_pause_torrent(self):
        """Test pausing a torrent"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/pause", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        client.pause_torrent("abc123")
        assert len(responses.calls) == 2

    @responses.activate
    def test_resume_torrent(self):
        """Test resuming a torrent"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/resume", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        client.resume_torrent("abc123")
        assert len(responses.calls) == 2

    @responses.activate
    def test_add_torrent_file(self, tmp_path):
        """Test adding a torrent file"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/add", status=200)
        
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"fake torrent data")
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.add_torrent_file(str(torrent_file), save_path="/downloads")
        assert result == True
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_preferences(self):
        """Test getting qBittorrent preferences"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(
            responses.GET,
            "http://localhost:8080/api/v2/app/preferences",
            json={"save_path": "/downloads", "temp_path": "/incomplete"},
            status=200
        )
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        prefs = client.get_preferences()
        assert prefs["save_path"] == "/downloads"
        assert prefs["temp_path"] == "/incomplete"

    @responses.activate
    def test_set_preferences(self):
        """Test setting qBittorrent preferences"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/app/setPreferences", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.set_preferences({"save_path": "/new/path"})
        assert result == True

    @responses.activate
    def test_create_category(self):
        """Test creating a category"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/createCategory", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.create_category("movies")
        assert result == True

    @responses.activate
    def test_set_category_save_path(self):
        """Test setting category save path"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/editCategory", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.set_category_save_path("movies", "/media/movies")
        assert result == True

    @responses.activate
    def test_get_categories(self):
        """Test getting all categories"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(
            responses.GET,
            "http://localhost:8080/api/v2/torrents/categories",
            json={"movies": {"savePath": "/media/movies"}},
            status=200
        )
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        cats = client.get_categories()
        assert "movies" in cats
        assert cats["movies"]["savePath"] == "/media/movies"

    @responses.activate
    def test_pause_torrents_list(self):
        """Test pausing multiple torrents with list"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/pause", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.pause_torrents(["abc123", "def456"])
        assert result == True

    @responses.activate
    def test_resume_torrents_list(self):
        """Test resuming multiple torrents with list"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/resume", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.resume_torrents(["abc123", "def456"])
        assert result == True

    @responses.activate
    def test_set_torrent_category(self):
        """Test setting category for torrents"""
        from common import QBitClient
        
        responses.add(responses.POST, "http://localhost:8080/api/v2/auth/login", body="Ok.", status=200)
        responses.add(responses.POST, "http://localhost:8080/api/v2/torrents/setCategory", status=200)
        
        client = QBitClient("http://localhost:8080", "admin", "pass")
        result = client.set_torrent_category(["abc123", "def456"], "tv shows")
        assert result == True
