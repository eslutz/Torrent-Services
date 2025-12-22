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

def test_recheck_all_rechecks_all_torrents():
    client = MagicMock()
    client.get_torrents.return_value = [
        {'hash': 'abc', 'name': 'Test1'},
        {'hash': 'def', 'name': 'Test2'}
    ]
    with patch('builtins.print'):
        manage_torrents.recheck_all(client)
    client.recheck_torrent.assert_called_once_with('abc|def')

def test_announce_all_reannounces_all():
    client = MagicMock()
    client.get_torrents.return_value = [
        {'hash': 'abc', 'name': 'Test1'},
        {'hash': 'def', 'name': 'Test2'}
    ]
    with patch('builtins.print'):
        manage_torrents.announce_all(client)
    client.reannounce_torrent.assert_called_once_with('abc|def')

def test_delete_broken_deletes_stalled_with_no_working_trackers():
    client = MagicMock()
    client.get_torrents.return_value = [
        {'hash': 'abc', 'name': 'Broken', 'state': 'stalledDL'},
        {'hash': 'def', 'name': 'Working', 'state': 'downloading'}
    ]
    client.get_trackers.return_value = [
        {'status': 0},  # Not working
        {'status': 1}   # Not working
    ]
    with patch('builtins.print'):
        manage_torrents.delete_broken(client, delete_files=False)
    client.delete_torrents.assert_called_once()
    args = client.delete_torrents.call_args[0]
    assert 'abc' in args[0]
    assert args[1] == False


