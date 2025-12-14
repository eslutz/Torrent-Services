import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_radarr


class TestSetupRadarr(unittest.TestCase):
    @patch("setup_radarr.requests.get")
    def test_get_schema_for_client(self, mock_get):
        mock_get.return_value.json.return_value = [{"implementation": "TestImpl", "fields": []}]
        schema = setup_radarr.get_schema_for_client("TestImpl", "api")
        assert schema["implementation"] == "TestImpl"

    @patch("setup_radarr.get_schema_for_client")
    @patch("setup_radarr.requests.post")
    @patch("setup_radarr.requests.get")
    def test_configure_download_clients_create(self, mock_get, mock_post, mock_schema):
        mock_get.return_value.json.return_value = []
        mock_schema.return_value = {"configContract": "contract", "fields": []}

        with patch.dict(
            setup_radarr.RADARR_CONFIG,
            {"download_clients": [{"name": "Client", "implementation": "Impl", "protocol": "torrent"}]},
            clear=True,
        ):
            setup_radarr.configure_download_clients("key")

        mock_post.assert_called_once()

    @patch("setup_radarr.configure_download_clients")
    @patch("setup_radarr.configure_root_folders")
    @patch("setup_radarr.configure_config_endpoint")
    @patch("setup_radarr.disable_analytics")
    @patch("setup_radarr.wait_for_service")
    @patch("setup_radarr.get_api_key")
    def test_main(self, mock_get_api_key, mock_wait, mock_disable, mock_config_endpoint, mock_roots, mock_downloads):
        mock_get_api_key.return_value = "key"
        setup_radarr.RADARR_CONFIG = {
            "media_management": {},
            "naming": {},
            "root_folders": [{"path": "/movies"}],
            "download_clients": [{"name": "Client"}],
        }

        setup_radarr.main()

        mock_get_api_key.assert_called_with("RADARR_API_KEY")
        mock_wait.assert_called_once()
        mock_disable.assert_called_once()
        assert mock_config_endpoint.call_count == 2
        mock_roots.assert_called_once()
        mock_downloads.assert_called_once()


if __name__ == "__main__":
    unittest.main()
