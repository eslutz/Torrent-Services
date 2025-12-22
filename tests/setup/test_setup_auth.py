import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

import setup_auth


class TestGenerateGluetunApikey:
    @patch("setup_auth.subprocess.check_output")
    def test_generate_gluetun_apikey_success(self, mock_check_output):
        """Test successful API key generation"""
        mock_check_output.return_value = b"test_api_key_12345\n"

        result = setup_auth.generate_gluetun_apikey()

        assert result == "test_api_key_12345"
        mock_check_output.assert_called_once()

    @patch("setup_auth.subprocess.check_output")
    def test_generate_gluetun_apikey_failure(self, mock_check_output):
        """Test API key generation failure"""
        mock_check_output.side_effect = Exception("Docker error")

        result = setup_auth.generate_gluetun_apikey()

        assert result is None


class TestSetupGluetunControlServer:
    @patch("setup_auth.generate_gluetun_apikey")
    def test_setup_gluetun_success(self, mock_generate):
        """Test successful setup just returns generated key"""
        mock_generate.return_value = "new_api_key_xyz"

        result = setup_auth.setup_gluetun_control_server()

        assert result == "new_api_key_xyz"
        mock_generate.assert_called_once()

    @patch("setup_auth.generate_gluetun_apikey")
    def test_setup_gluetun_generate_failure(self, mock_generate):
        """Test failure when key generation fails"""
        mock_generate.return_value = None

        result = setup_auth.setup_gluetun_control_server()

        assert result is None
        mock_generate.assert_called_once()


class TestUpdateEnvApikey:
    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="EXISTING_VAR=value\n")
    def test_update_env_apikey_new_key(self, mock_file, mock_exists):
        """Test adding new API key to .env"""
        mock_exists.return_value = True

        setup_auth.update_env_apikey("test_key_123")

        # Verify file was opened for reading and writing
        assert mock_file.call_count >= 1

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="CONTROL_APIKEY=existing_key\n")
    def test_update_env_apikey_already_exists(self, mock_file, mock_exists):
        """Test updating when API key already exists in .env"""
        mock_exists.return_value = True

        setup_auth.update_env_apikey("new_key_123")

        # Should read and then write the update
        assert mock_file.call_count >= 2
        # Verify write content contains new key
        handle = mock_file()
        handle.write.assert_called()
        args = handle.write.call_args[0][0]
        assert 'CONTROL_APIKEY="new_key_123"' in args

    @patch("pathlib.Path.exists")
    def test_update_env_apikey_file_not_found(self, mock_exists):
        """Test error when .env file doesn't exist"""
        mock_exists.return_value = False

        # Should not raise, just return
        setup_auth.update_env_apikey("test_key_123")

    @patch("pathlib.Path.exists")
    def test_update_env_apikey_none_key(self, mock_exists):
        """Test skipping when API key is None"""
        setup_auth.update_env_apikey(None)

        # Should not attempt any file operations


class TestGetQbittorrentTempPassword:
    @patch("setup_auth.subprocess.check_output")
    def test_get_qbittorrent_temp_password_success(self, mock_check_output):
        """Test extracting temporary password from logs"""
        mock_check_output.return_value = b"Some log output\ntemporary password is provided for this session: TempPass123\nMore logs"

        result = setup_auth.get_qbittorrent_temp_password()

        assert result == "TempPass123"

    @patch("setup_auth.subprocess.check_output")
    def test_get_qbittorrent_temp_password_not_found(self, mock_check_output):
        """Test when temporary password not in logs"""
        mock_check_output.return_value = b"Some log output\nNo password here"

        result = setup_auth.get_qbittorrent_temp_password()

        assert result is None

    @patch("setup_auth.subprocess.check_output")
    def test_get_qbittorrent_temp_password_error(self, mock_check_output):
        """Test error handling when docker logs fails"""
        mock_check_output.side_effect = Exception("Docker error")

        result = setup_auth.get_qbittorrent_temp_password()

        assert result is None



class TestSetupQbittorrentAuth:
    @patch("setup_auth.QBitClient")
    @patch("setup_auth.get_qbittorrent_temp_password")
    def test_setup_qbittorrent_auth_env_credentials_success(self, mock_get_temp, mock_qbit):
        """Test .env credentials succeed"""
        mock_client = MagicMock()
        mock_client.login.return_value = True
        mock_qbit.return_value = mock_client
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "user", "pass")
        mock_client.login.assert_called_once()
        mock_get_temp.assert_not_called()

    @patch("setup_auth.QBitClient")
    @patch("setup_auth.get_qbittorrent_temp_password")
    def test_setup_qbittorrent_auth_temp_password_success(self, mock_get_temp, mock_qbit):
        """Test .env credentials fail, temp password succeeds and updates credentials"""
        # First QBitClient (env) fails, second (temp) succeeds
        env_client = MagicMock()
        env_client.login.return_value = False
        temp_client = MagicMock()
        temp_client.login.return_value = True
        mock_qbit.side_effect = [env_client, temp_client]
        mock_get_temp.return_value = "TempPass123"
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "user", "pass")
        assert mock_qbit.call_count == 2
        temp_client.set_preferences.assert_any_call({"bypass_auth_subnet_whitelist_enabled": False})
        temp_client.set_preferences.assert_any_call({"web_ui_username": "user", "web_ui_password": "pass"})

    @patch("setup_auth.QBitClient")
    @patch("setup_auth.get_qbittorrent_temp_password")
    def test_setup_qbittorrent_auth_failure(self, mock_get_temp, mock_qbit):
        """Test both .env and temp password fail"""
        env_client = MagicMock()
        env_client.login.return_value = False
        temp_client = MagicMock()
        temp_client.login.return_value = False
        mock_qbit.side_effect = [env_client, temp_client]
        mock_get_temp.return_value = "TempPass123"
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "user", "pass")
        assert mock_qbit.call_count == 2
        temp_client.set_preferences.assert_not_called()



# Playwright-based tests for setup_auth_for_service would require more advanced mocking or integration testing.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
