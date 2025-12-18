import os
import pytest
from unittest.mock import patch, MagicMock
from scripts.utilities import manage_storage

class DummyClient:
    def __init__(self):
        self.prefs = {}
        self.locations = []
    def set_preferences(self, prefs):
        self.prefs.update(prefs)
        return True
    def get_torrents(self):
        return [
            {'hash': 'abc', 'name': 'Test', 'amount_left': 100, 'save_path': '/media/downloads'},
            {'hash': 'def', 'name': 'Done', 'amount_left': 0, 'save_path': '/media/downloads'}
        ]
    def set_location(self, hash, new_path):
        self.locations.append((hash, new_path))

@patch('scripts.utilities.manage_storage.log')
def test_update_qbittorrent_paths_sets_both_paths(mock_log):
    client = DummyClient()
    manage_storage.update_qbittorrent_paths(client, '/media2')
    assert client.prefs['save_path'] == '/media2/downloads'
    assert client.prefs['temp_path'] == '/media2/incomplete'
    assert client.prefs['temp_path_enabled'] is True

@patch('scripts.utilities.manage_storage.log')
def test_move_incomplete_torrents_moves_only_incomplete(mock_log):
    client = DummyClient()
    manage_storage.move_incomplete_torrents(client, '/media2')
    # Only the incomplete torrent should be moved
    assert client.locations == [('abc', '/media2/downloads')]

@patch('scripts.utilities.manage_storage.log')
def test_update_env_file_add_and_remove(mock_log, tmp_path):
    env_path = tmp_path / '.env'
    env_path.write_text('DATA_DIR="/media"\n')
    manage_storage.ENV_FILE = str(env_path)
    var, mount = manage_storage.update_env_file('add', '/mnt/new')
    assert 'DATA_DIR_' in var
    assert mount.startswith('/media')
    var2, mount2 = manage_storage.update_env_file('remove', '/mnt/new')
    assert var2 == var
    assert mount2 == mount
    # Should be removed from file
    assert '/mnt/new' not in env_path.read_text()
