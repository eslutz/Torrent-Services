import importlib
import pytest
import sys
from pathlib import Path

# Add scripts/setup to path for direct imports
test_dir = Path(__file__).parent
setup_dir = test_dir.parent.parent / "scripts" / "setup"
sys.path.insert(0, str(setup_dir))

# Test that setup.config.json is valid JSON and contains expected keys
def test_setup_config_json_valid():

    import json
    config_path = setup_dir / "setup.config.json"
    with open(config_path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    # Check for at least one expected key
    assert any(k in data for k in ["prowlarr", "sonarr", "radarr", "qbittorrent"])


import sys
import importlib
configure_library = importlib.import_module("configure_library")


def test_trigger_command_success(monkeypatch):
    called = {}
    monkeypatch.setattr(configure_library, "log", lambda msg, level="INFO": called.setdefault("log", (msg, level)))
    monkeypatch.setattr(configure_library, "get_headers", lambda k: {"Authorization": "x"})
    class DummyResp:
        def raise_for_status(self):
            called["raised"] = True
    monkeypatch.setattr(configure_library.requests, "post", lambda *a, **kw: DummyResp())
    configure_library.trigger_command("url", "key", "cmd", foo=1)
    assert "log" in called and "raised" in called

def test_trigger_command_exception(monkeypatch):
    monkeypatch.setattr(configure_library, "log", lambda msg, level="INFO": None)
    monkeypatch.setattr(configure_library, "get_headers", lambda k: {})
    def raise_exc(*a, **kw):
        raise Exception("fail")
    monkeypatch.setattr(configure_library.requests, "post", raise_exc)
    configure_library.trigger_command("url", "key", "cmd")

def test_main(monkeypatch):
    monkeypatch.setattr(configure_library, "get_api_key", lambda k: "key")
    monkeypatch.setattr(configure_library, "wait_for_service", lambda *a, **kw: None)
    monkeypatch.setattr(configure_library, "configure_root_folders", lambda *a, **kw: None)
    monkeypatch.setattr(configure_library, "configure_config_endpoint", lambda *a, **kw: None)
    monkeypatch.setattr(configure_library, "trigger_command", lambda *a, **kw: None)
    configure_library.main()
