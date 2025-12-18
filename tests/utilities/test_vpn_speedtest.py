import pytest
from unittest.mock import patch, MagicMock
from scripts.utilities import vpn_speedtest

def test_log_prints(monkeypatch):
    tester = vpn_speedtest.VPNSpeedTest('dummy', json_output=False)
    with patch('builtins.print') as mock_print:
        tester.log('msg', color=vpn_speedtest.GREEN)
        assert any('msg' in str(call) for call in mock_print.call_args_list)

def test_get_host_ip_returns(monkeypatch):
    monkeypatch.setattr(vpn_speedtest.requests, 'get', lambda url, timeout=5: MagicMock(status_code=200, json=lambda: {'ip': '1.2.3.4'}))
    tester = vpn_speedtest.VPNSpeedTest('dummy', json_output=True)
    assert tester.get_host_ip() == '1.2.3.4'
