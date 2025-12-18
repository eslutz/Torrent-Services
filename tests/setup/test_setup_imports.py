import pytest
import importlib
import os
import sys
from pathlib import Path

# Add scripts/setup to path for direct imports
test_dir = Path(__file__).parent
setup_dir = test_dir.parent.parent / "scripts" / "setup"
sys.path.insert(0, str(setup_dir))

# Test that all setup scripts are importable and have a main function if expected
SETUP_SCRIPTS = [
    "bootstrap",
    "configure_library",
    "extract_api_keys",
    "setup_auth",
    "setup_bazarr",
    "setup_prowlarr",
    "setup_qbittorrent",
    "setup_radarr",
    "setup_sonarr",
]

def test_import_all_setup_scripts():
    for script in SETUP_SCRIPTS:
        mod = importlib.import_module(script)
        assert mod is not None

def test_main_functions_exist():
    for script in SETUP_SCRIPTS:
        mod = importlib.import_module(script)
        # Not all scripts need a main, but most do
        if hasattr(mod, "main"):
            assert callable(mod.main)

def test_config_file_exists():
    config_path = setup_dir / "setup.config.json"
    assert config_path.exists()
    assert config_path.stat().st_size > 0
