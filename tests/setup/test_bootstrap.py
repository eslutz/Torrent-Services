import os
import sys
import pytest
import responses
from unittest.mock import patch, MagicMock

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
