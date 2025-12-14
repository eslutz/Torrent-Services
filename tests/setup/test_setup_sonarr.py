import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_sonarr


class TestSetupSonarr(unittest.TestCase):
    @patch("setup_sonarr.configure_root_folders")
    @patch("setup_sonarr.configure_download_clients")
    @patch("setup_sonarr.configure_config_endpoint")
    @patch("setup_sonarr.disable_analytics")
    @patch("setup_sonarr.wait_for_service")
    @patch("setup_sonarr.get_api_key")
    def test_main(self, mock_get_api_key, mock_wait, mock_disable, mock_config_endpoint, mock_download, mock_roots):
        mock_get_api_key.return_value = "test"

        setup_sonarr.SONARR_CONFIG = {
            "media_management": {"renameEpisodes": True},
            "naming": {"renameEpisodes": True},
            "download_clients": [{"name": "qbittorrent"}],
            "root_folders": [{"path": "/tv"}],
        }

        setup_sonarr.main()

        mock_get_api_key.assert_called_with("SONARR_API_KEY")
        mock_wait.assert_called_once()
        mock_disable.assert_called_once()
        assert mock_config_endpoint.call_count == 2
        mock_download.assert_called_once()
        mock_roots.assert_called_once()


if __name__ == "__main__":
    unittest.main()
