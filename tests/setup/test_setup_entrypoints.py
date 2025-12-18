import importlib
import pytest
from pathlib import Path
import sys

# Add scripts/setup to path for direct imports
test_dir = Path(__file__).parent
setup_dir = test_dir.parent.parent / "scripts" / "setup"
sys.path.insert(0, str(setup_dir))

@pytest.mark.parametrize("script,main_expected", [
    ("bootstrap", True),
    ("configure_library", False),
    ("extract_api_keys", True),
    ("setup_auth", True),
    ("setup_bazarr", True),
    ("setup_prowlarr", True),
    ("setup_qbittorrent", True),
    ("setup_radarr", True),
    ("setup_sonarr", True),
])
def test_script_main_entrypoint(script, main_expected):
    mod = importlib.import_module(script)
    if main_expected:
        assert hasattr(mod, "main") and callable(mod.main)
    else:
        assert mod is not None
