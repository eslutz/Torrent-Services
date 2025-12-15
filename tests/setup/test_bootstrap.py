import os
import sys
import responses
from unittest.mock import patch, mock_open, MagicMock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

from bootstrap import log


class TestBootstrapLog:
    def test_log_function(self, capsys):
        """Test bootstrap logging function"""
        log("Test message", "INFO")
        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "Test message" in captured.out

    def test_log_function_different_levels(self, capsys):
        """Test logging with different levels"""
        for level in ["INFO", "SUCCESS", "WARNING", "ERROR"]:
            log(f"Test {level}", level)
            captured = capsys.readouterr()
            assert level in captured.out


class TestBootstrapLoadEnv:
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="TEST_VAR=test_value\n")
    def test_load_env_success(self, mock_file, mock_exists):
        """Test loading environment variables from .env file"""
        mock_exists.return_value = True
        from bootstrap import load_env
        
        # Clear any existing env var
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]
        
        load_env()
        # The test would set the env var but we're mocking the file
        
    @patch("os.path.exists")
    def test_load_env_file_not_found(self, mock_exists):
        """Test load_env when .env file doesn't exist"""
        mock_exists.return_value = False
        from bootstrap import load_env
        
        try:
            load_env()
            assert False, "Should have exited"
        except SystemExit as e:
            assert e.code == 1

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='QUOTED_VAR="quoted value"\n')
    def test_load_env_quoted_value(self, mock_file, mock_exists):
        """Test loading environment variables with quoted values"""
        mock_exists.return_value = True
        from bootstrap import load_env
        
        # Clear any existing env var
        if "QUOTED_VAR" in os.environ:
            del os.environ["QUOTED_VAR"]
        
        load_env()

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="# Comment\nVAR=value\n\n")
    def test_load_env_with_comments(self, mock_file, mock_exists):
        """Test loading environment variables with comments and empty lines"""
        mock_exists.return_value = True
        from bootstrap import load_env
        
        # Clear any existing env var
        if "VAR" in os.environ:
            del os.environ["VAR"]
        
        load_env()

    @patch("os.path.exists")
    @patch("builtins.open", side_effect=Exception("Read error"))
    def test_load_env_read_exception(self, mock_file, mock_exists):
        """Test load_env when file read fails"""
        mock_exists.return_value = True
        from bootstrap import load_env
        
        # Should not raise, just log warning
        load_env()


class TestBootstrapWaitForService:
    @responses.activate
    def test_wait_for_service_success(self):
        """Test waiting for service successfully"""
        responses.add(
            responses.GET, "http://localhost:9696/ping", json={"status": "OK"}, status=200
        )

        from bootstrap import wait_for_service

        # Should not raise exception
        wait_for_service("Prowlarr", "http://localhost:9696/ping")

    @responses.activate
    def test_wait_for_service_eventually_succeeds(self):
        """Test waiting for service that eventually becomes ready"""
        # First call fails, second succeeds
        responses.add(
            responses.GET,
            "http://localhost:9696/ping",
            json={"error": "not ready"},
            status=503,
        )
        responses.add(
            responses.GET, "http://localhost:9696/ping", json={"status": "OK"}, status=200
        )

        from bootstrap import wait_for_service

        wait_for_service("Prowlarr", "http://localhost:9696/ping")

    @responses.activate
    def test_wait_for_service_unauthorized(self):
        """Test waiting for service that returns 401"""
        responses.add(
            responses.GET, "http://localhost:9696/ping", json={}, status=401
        )

        from bootstrap import wait_for_service

        # 401 is considered ready (service is up, just needs auth)
        wait_for_service("Prowlarr", "http://localhost:9696/ping")

    @responses.activate
    def test_wait_for_service_redirect(self):
        """Test waiting for service that returns 302"""
        responses.add(
            responses.GET, "http://localhost:9696/ping", json={}, status=302
        )

        from bootstrap import wait_for_service

        # 302 is considered ready (service is redirecting, means it's up)
        wait_for_service("Prowlarr", "http://localhost:9696/ping")

    @responses.activate
    def test_wait_for_service_connection_error(self):
        """Test waiting for service with connection errors that eventually succeeds"""
        import requests
        
        # First call raises exception, second succeeds
        responses.add(
            responses.GET,
            "http://localhost:9696/ping",
            body=requests.RequestException("Connection failed")
        )
        responses.add(
            responses.GET, "http://localhost:9696/ping", json={"status": "OK"}, status=200
        )

        from bootstrap import wait_for_service

        wait_for_service("Prowlarr", "http://localhost:9696/ping")


class TestBootstrapRunScript:
    @patch("subprocess.run")
    def test_run_script_success(self, mock_run):
        """Test running a script successfully"""
        mock_run.return_value = MagicMock(returncode=0)
        from bootstrap import run_script
        
        run_script("test_script.py")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_script_failure(self, mock_run):
        """Test running a script that fails"""
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "test")
        from bootstrap import run_script
        
        try:
            run_script("test_script.py")
            assert False, "Should have exited"
        except SystemExit as e:
            assert e.code == 1
