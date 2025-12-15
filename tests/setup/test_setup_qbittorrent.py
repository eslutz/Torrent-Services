import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_qbittorrent


class TestSetupQBittorrent(unittest.TestCase):
    @patch("setup_qbittorrent.requests.Session")
    @patch("setup_qbittorrent.get_api_key")
    @patch("setup_qbittorrent.configure_preferences")
    @patch("setup_qbittorrent.authenticate")
    @patch("setup_qbittorrent.wait_for_qbittorrent")
    def test_main(self, mock_wait, mock_auth, mock_configure, mock_get_key, mock_session_cls):
        mock_get_key.side_effect = ["user", "pass"]
        mock_auth.return_value = MagicMock()
        setup_qbittorrent.main()
        mock_wait.assert_called_once()
        mock_auth.assert_called_once()
        mock_configure.assert_called_once()

    @patch("setup_qbittorrent.requests.get")
    def test_wait_for_qbittorrent_success(self, mock_get):
        mock_get.return_value.status_code = 200
        setup_qbittorrent.wait_for_qbittorrent()
        mock_get.assert_called()

    @patch("sys.exit")
    @patch("setup_qbittorrent.requests.get", side_effect=Exception("boom"))
    @patch("time.sleep", side_effect=lambda *_: None)
    def test_wait_for_qbittorrent_failure(self, mock_sleep, mock_get, mock_exit):
        setup_qbittorrent.wait_for_qbittorrent()
        mock_exit.assert_called_with(1)


if __name__ == "__main__":
    unittest.main()
