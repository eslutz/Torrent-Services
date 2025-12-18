import pytest
from unittest.mock import patch, MagicMock
from scripts.utilities import manage_torrents

def test_fix_paths_fixes_only_wrong(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.locations = []
        def get_torrents(self):
            return [
                {'name': 'A', 'save_path': '/downloads/A', 'hash': 'abc'},
                {'name': 'B', 'save_path': '/media/downloads', 'hash': 'def'}
            ]
        def set_location(self, h, p):
            self.locations.append((h, p))
    config = MagicMock()
    config.default_save_path = '/media/downloads'
    client = DummyClient()
    manage_torrents.fix_paths(client, config)
    assert ('abc', '/media/downloads') in client.locations
    assert ('def', '/media/downloads') not in client.locations

def test_add_missing_adds(monkeypatch, tmp_path):
    class DummyClient:
        def add_torrent_file(self, f, p):
            return True
    config = MagicMock()
    config.default_scan_path = str(tmp_path)
    config.default_save_path = '/media/downloads'
    # Create dummy .torrent files
    (tmp_path / 'a.torrent').write_text('x')
    (tmp_path / 'b.torrent').write_text('y')
    with patch('builtins.print') as mock_print:
        manage_torrents.add_missing(DummyClient(), config)
        assert any('Processed' in str(call) for call in mock_print.call_args_list)
