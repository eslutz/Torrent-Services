import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_bazarr


class TestSetupBazarr(unittest.TestCase):
    @patch("setup_bazarr.requests.post")
    @patch("setup_bazarr.requests.get")
    def test_configure_radarr(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = {
            "general": {"use_radarr": False},
            "radarr": {"apikey": "old"},
        }

        with patch.dict(
            setup_bazarr.BAZARR_CONFIG,
            {"radarr": {"ip": "radarr", "movies_sync": 60}, "general": {}},
            clear=True,
        ):
            setup_bazarr.configure_radarr("bazarr_key", "radarr_key")

        mock_post.assert_called_once()

    @patch("setup_bazarr.requests.post")
    def test_configure_general_settings(self, mock_post):
        with patch.dict(setup_bazarr.BAZARR_CONFIG, {"general": {"setting": "value"}}, clear=True):
            setup_bazarr.configure_general_settings("key")

        mock_post.assert_called_once()

    @patch("setup_bazarr.requests.put")
    @patch("setup_bazarr.requests.post")
    @patch("setup_bazarr.requests.get")
    def test_configure_language_profiles(self, mock_get, mock_post, mock_put):
        mock_get.return_value.json.return_value = []
        with patch.dict(
            setup_bazarr.BAZARR_CONFIG,
            {"language_profiles": [{"name": "English", "languages": [{"language": "en"}]}]},
            clear=True,
        ):
            setup_bazarr.configure_language_profiles("key")

        mock_put.assert_called_once()

    @patch("setup_bazarr.requests.post")
    @patch("setup_bazarr.requests.get")
    @patch.dict(os.environ, {"SERVICE_USER": "user", "OPENSUBTITLESCOM_PASS": "pass"})
    def test_configure_providers(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = []
        with patch.dict(
            setup_bazarr.BAZARR_CONFIG,
            {"general": {"enabled_providers": ["opensubtitlescom"]}},
            clear=True,
        ):
            setup_bazarr.configure_providers("key")

        mock_post.assert_called_once()

    @patch("setup_bazarr.configure_providers")
    @patch("setup_bazarr.configure_language_profiles")
    @patch("setup_bazarr.configure_general_settings")
    @patch("setup_bazarr.configure_radarr")
    @patch("setup_bazarr.configure_sonarr")
    @patch("setup_bazarr.wait_for_bazarr")
    @patch("setup_bazarr.get_api_key")
    def test_main(self, mock_get_key, mock_wait, mock_sonarr, mock_radarr, mock_general, mock_profiles, mock_providers):
        mock_get_key.return_value = "key"
        setup_bazarr.main()
        mock_wait.assert_called_once()
        mock_sonarr.assert_called_once()
        mock_radarr.assert_called_once()
        mock_general.assert_called_once()
        mock_profiles.assert_called_once()
        mock_providers.assert_called_once()


if __name__ == "__main__":
    unittest.main()
