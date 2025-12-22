import pytest
from unittest.mock import patch, MagicMock
from scripts.utilities import check_torrent_status

def test_check_all_prints_table(monkeypatch):
    class DummyClient:
        def get_torrents(self):
            return [
                {'name': 'A', 'state': 'error', 'progress': 0.5, 'error_type': 'Disk'},
                {'name': 'B', 'state': 'stalledDL', 'progress': 0.1},
                {'name': 'C', 'state': 'missingFiles', 'progress': 0.9}
            ]
    monkeypatch.setattr(check_torrent_status, 'Config', lambda: MagicMock())
    monkeypatch.setattr(check_torrent_status, 'QBitClient', lambda *a, **kw: DummyClient())
    with patch('builtins.print') as mock_print:
        check_torrent_status.check_all(DummyClient())
        assert any('A' in str(call) for call in mock_print.call_args_list)

def test_inspect_torrent_prints(monkeypatch):
    class DummyClient:
        def get_torrents(self):
            return [{'hash': 'abc', 'name': 'Test', 'state': 'error', 'progress': 0.5, 'save_path': '/media', 'content_path': '/media/file', 'dlspeed': 0, 'num_seeds': 1, 'num_complete': 1, 'num_leechs': 0, 'num_incomplete': 0}]
        def get_trackers(self, h):
            return [{'url': 'tracker', 'status': 2, 'msg': '', 'num_peers': 1}]
    with patch('builtins.print') as mock_print:
        check_torrent_status.inspect_torrent(DummyClient(), 'abc')
        assert any('Inspecting' in str(call) for call in mock_print.call_args_list)

def test_inspect_torrent_not_found():
    class DummyClient:
        def get_torrents(self):
            return [{'hash': 'abc', 'name': 'Test'}]
    with patch('builtins.print') as mock_print:
        check_torrent_status.inspect_torrent(DummyClient(), 'nonexistent')
        assert any('not found' in str(call) for call in mock_print.call_args_list)

def test_print_table_formats_correctly():
    headers = ['Col1', 'Col2']
    rows = [['val1', 'val2'], ['val3', 'val4']]
    with patch('builtins.print') as mock_print:
        check_torrent_status.print_table(headers, rows)
        # Should print header and rows
        assert mock_print.call_count >= 3
