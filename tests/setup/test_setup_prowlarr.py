import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_prowlarr


class TestSetupProwlarr(unittest.TestCase):
    @patch("setup_prowlarr.requests.post")
    @patch("setup_prowlarr.requests.get")
    def test_get_tag_id_create(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = []
        mock_post.return_value.json.return_value = {"id": 5}
        tag_id = setup_prowlarr.get_tag_id("new", "key")
        assert tag_id == 5

    @patch("setup_prowlarr.requests.post")
    @patch("setup_prowlarr.requests.get")
    def test_configure_proxy_create(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = []

        with patch("setup_prowlarr.get_tag_id", return_value=1):
            setup_prowlarr.configure_proxy("key")

        mock_post.assert_called_once()

    @patch("setup_prowlarr.requests.get")
    def test_get_schema_for_indexer(self, mock_get):
        mock_get.return_value.json.return_value = [{"name": "Test", "id": 1}]
        schema = setup_prowlarr.get_schema_for_indexer("Test", "key")
        assert schema["id"] == 1

    @patch("setup_prowlarr.get_schema_for_indexer")
    @patch("setup_prowlarr.requests.post")
    @patch("setup_prowlarr.requests.get")
    def test_configure_indexers_create(self, mock_get, mock_post, mock_schema):
        mock_get.return_value.json.return_value = []
        mock_schema.return_value = {
            "implementation": "Impl",
            "implementationName": "Impl",
            "configContract": "ImplSettings",
            "fields": [],
            "protocol": "torrent",
        }

        with patch.dict(setup_prowlarr.PROWLARR_CONFIG, {"indexers": [{"name": "Indexer"}]}, clear=True):
            setup_prowlarr.configure_indexers("key")

        mock_post.assert_called_once()

    @patch("setup_prowlarr.requests.post")
    @patch("setup_prowlarr.requests.get")
    @patch.dict(os.environ, {"SONARR_API_KEY": "sonarr", "RADARR_API_KEY": "radarr"})
    def test_configure_apps(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = []
        setup_prowlarr.configure_apps("key")
        assert mock_post.call_count == 2

    @patch("setup_prowlarr.configure_apps")
    @patch("setup_prowlarr.configure_indexers")
    @patch("setup_prowlarr.configure_proxy")
    @patch("setup_prowlarr.disable_analytics")
    @patch("setup_prowlarr.wait_for_service")
    @patch("setup_prowlarr.get_api_key")
    def test_main(self, mock_get_key, mock_wait, mock_disable, mock_proxy, mock_indexers, mock_apps):
        mock_get_key.return_value = "key"
        setup_prowlarr.main()
        mock_wait.assert_called_once()
        mock_disable.assert_called_once()
        mock_proxy.assert_called_once()
        mock_indexers.assert_called_once()
        mock_apps.assert_called_once()


if __name__ == "__main__":
    unittest.main()
