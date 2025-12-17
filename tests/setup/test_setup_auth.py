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
    @patch("builtins.open", new_callable=mock_open, read_data="GLUETUN_CONTROL_APIKEY=existing_key\n")
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
        assert 'GLUETUN_CONTROL_APIKEY="new_key_123"' in args

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


class TestQbittorrentLogin:
    @patch("setup_auth.requests.Session")
    def test_qbittorrent_login_success(self, mock_session_cls):
        """Test successful login"""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.text = "Ok."
        mock_session.get.return_value.status_code = 200
        
        result = setup_auth.qbittorrent_login("http://localhost:8080", "user", "pass")
        
        assert result is not None

    @patch("setup_auth.requests.Session")
    def test_qbittorrent_login_failure(self, mock_session_cls):
        """Test failed login"""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value.status_code = 401
        
        result = setup_auth.qbittorrent_login("http://localhost:8080", "user", "pass")
        
        assert result is None

    @patch("setup_auth.requests.Session")
    def test_qbittorrent_login_fails_response(self, mock_session_cls):
        """Test when login returns 'Fails.' response"""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.text = "Fails."
        
        result = setup_auth.qbittorrent_login("http://localhost:8080", "user", "pass")
        
        assert result is None


class TestSetupQbittorrentAuth:
    @patch("setup_auth.qbittorrent_login")
    def test_setup_qbittorrent_auth_already_configured(self, mock_login):
        """Test when credentials are already configured"""
        mock_session = MagicMock()
        mock_login.return_value = mock_session
        
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "user", "pass")
        
        # Should only call login once with target credentials
        assert mock_login.call_count == 1

    @patch("setup_auth.get_qbittorrent_temp_password")
    @patch("setup_auth.qbittorrent_login")
    def test_setup_qbittorrent_auth_with_temp_password(self, mock_login, mock_get_temp):
        """Test updating credentials using temporary password"""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_login.side_effect = [None, mock_session]  # First fails, second succeeds
        mock_get_temp.return_value = "TempPass123"
        
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "newuser", "newpass")
        
        # Should call login twice and try to update preferences
        assert mock_login.call_count == 2
        assert mock_session.post.call_count >= 1

    @patch("setup_auth.get_qbittorrent_temp_password")
    @patch("setup_auth.qbittorrent_login")
    def test_setup_qbittorrent_auth_no_credentials(self, mock_login, mock_get_temp):
        """Test error when no credentials available"""
        mock_login.return_value = None
        mock_get_temp.return_value = None
        
        setup_auth.setup_qbittorrent_auth("http://localhost:8080", "user", "pass")
        
        # Should attempt login twice


class TestSetupAuthForService:
    @patch("setup_auth.sync_playwright")
    def test_setup_auth_for_service_login_form_found(self, mock_playwright):
        """Test handling of login form"""
        mock_page = MagicMock()
        mock_page.is_visible.side_effect = [True, False]  # Username visible, then check again
        
        setup_auth.setup_auth_for_service(mock_page, "TestService", "http://localhost", "user", "pass")
        
        # Should attempt to fill form
        mock_page.fill.assert_called()

    @patch("setup_auth.sync_playwright")
    def test_setup_auth_for_service_no_login_form(self, mock_playwright):
        """Test when no login form found"""
        mock_page = MagicMock()
        mock_page.is_visible.return_value = False
        
        setup_auth.setup_auth_for_service(mock_page, "TestService", "http://localhost", "user", "pass")
        
        # Should check for dashboard elements instead
        mock_page.is_visible.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
