import os
import sys
import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts/setup"))

from extract_api_keys import extract_xml_key, extract_bazarr_key, update_env_file


class TestExtractXmlKey:
    def test_extract_xml_key_success(self, tmp_path):
        """Test extracting API key from XML config"""
        config_file = tmp_path / "config.xml"
        config_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<Config>
  <ApiKey>test_api_key_123</ApiKey>
  <Port>8989</Port>
</Config>"""
        )

        api_key = extract_xml_key(str(config_file))
        assert api_key == "test_api_key_123"

    def test_extract_xml_key_missing_file(self):
        """Test extracting from non-existent file"""
        api_key = extract_xml_key("/nonexistent/config.xml")
        assert api_key is None

    def test_extract_xml_key_no_key(self, tmp_path):
        """Test extracting from XML without API key"""
        config_file = tmp_path / "config.xml"
        config_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<Config>
  <Port>8989</Port>
</Config>"""
        )

        api_key = extract_xml_key(str(config_file))
        assert api_key is None

    def test_extract_xml_key_invalid_xml(self, tmp_path):
        """Test extracting from invalid XML"""
        config_file = tmp_path / "config.xml"
        config_file.write_text("This is not valid XML")

        api_key = extract_xml_key(str(config_file))
        assert api_key is None


class TestExtractBazarrKey:
    def test_extract_bazarr_key_success(self, tmp_path):
        """Test extracting API key from Bazarr YAML config"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
general:
  apikey: bazarr_test_key_456
  port: 6767
"""
        )

        api_key = extract_bazarr_key(str(config_file))
        assert api_key == "bazarr_test_key_456"

    def test_extract_bazarr_key_with_quotes(self, tmp_path):
        """Test extracting API key with quotes"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
general:
  apikey: 'bazarr_test_key_789'
  port: 6767
"""
        )

        api_key = extract_bazarr_key(str(config_file))
        assert api_key == "bazarr_test_key_789"

    def test_extract_bazarr_key_missing_file(self):
        """Test extracting from non-existent file"""
        api_key = extract_bazarr_key("/nonexistent/config.yaml")
        assert api_key is None

    def test_extract_bazarr_key_no_key(self, tmp_path):
        """Test extracting from config without API key"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
general:
  port: 6767
"""
        )

        api_key = extract_bazarr_key(str(config_file))
        assert api_key is None


class TestUpdateEnvFile:
    def test_update_env_file_new_key(self, tmp_path):
        """Test adding new key to .env file"""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=value\n")

        with pytest.MonkeyPatch.context() as m:
            m.setattr("extract_api_keys.ENV_FILE", str(env_file))
            result = update_env_file({"NEW_KEY": "new_value"})

        assert result is True
        content = env_file.read_text()
        assert 'NEW_KEY="new_value"' in content
        assert "EXISTING_KEY=value" in content

    def test_update_env_file_existing_key(self, tmp_path):
        """Test updating existing key in .env file"""
        env_file = tmp_path / ".env"
        env_file.write_text('SONARR_API_KEY="old_key"\nOTHER_KEY=value\n')

        with pytest.MonkeyPatch.context() as m:
            m.setattr("extract_api_keys.ENV_FILE", str(env_file))
            result = update_env_file({"SONARR_API_KEY": "new_key"})

        assert result is True
        content = env_file.read_text()
        assert 'SONARR_API_KEY="new_key"' in content
        assert 'SONARR_API_KEY="old_key"' not in content

    def test_update_env_file_multiple_keys(self, tmp_path):
        """Test updating multiple keys"""
        env_file = tmp_path / ".env"
        env_file.write_text('SONARR_API_KEY="old"\nRADARR_API_KEY="old2"\n')

        with pytest.MonkeyPatch.context() as m:
            m.setattr("extract_api_keys.ENV_FILE", str(env_file))
            result = update_env_file({"SONARR_API_KEY": "new1", "RADARR_API_KEY": "new2"})

        assert result is True
        content = env_file.read_text()
        assert 'SONARR_API_KEY="new1"' in content
        assert 'RADARR_API_KEY="new2"' in content

    def test_update_env_file_missing(self, tmp_path):
        """Test updating non-existent .env file"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("extract_api_keys.ENV_FILE", "/nonexistent/.env")
            result = update_env_file({"KEY": "value"})

        assert result is False

    def test_update_env_file_skip_none_values(self, tmp_path):
        """Test that None values are skipped"""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=value\n")

        with pytest.MonkeyPatch.context() as m:
            m.setattr("extract_api_keys.ENV_FILE", str(env_file))
            result = update_env_file({"NEW_KEY": None, "VALID_KEY": "valid"})

        assert result is True
        content = env_file.read_text()
        assert "NEW_KEY" not in content
        assert 'VALID_KEY="valid"' in content
