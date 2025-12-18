import os
import sys
import pytest
import setup_qbittorrent

def test_wait_for_qbittorrent_success(monkeypatch):
    class DummyResp:
        status_code = 200
    import requests
    monkeypatch.setattr(requests, "get", lambda url: DummyResp())
    setup_qbittorrent.wait_for_qbittorrent()

def test_wait_for_qbittorrent_failure(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda url: (_ for _ in ()).throw(Exception("boom")))
    called = {}
    def fake_exit(code):
        called['exit'] = code
    monkeypatch.setattr(sys, "exit", fake_exit)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    setup_qbittorrent.wait_for_qbittorrent()
    assert called['exit'] == 1


def test_authenticate_success(monkeypatch):
    class DummyClient:
        def __init__(self, *a, **kw):
            self.login_called = False
        def login(self):
            self.login_called = True
            return True
    monkeypatch.setattr(setup_qbittorrent, "QBitClient", lambda *a, **kw: DummyClient())
    monkeypatch.setattr(setup_qbittorrent, "get_api_key", lambda k: "x")
    result = setup_qbittorrent.authenticate()
    assert hasattr(result, "login_called")

def test_authenticate_failure(monkeypatch):
    class DummyClient:
        def login(self):
            return False
    monkeypatch.setattr(setup_qbittorrent, "QBitClient", lambda *a, **kw: DummyClient())
    monkeypatch.setattr(setup_qbittorrent, "get_api_key", lambda k: "x")
    called = {}
    monkeypatch.setattr(sys, "exit", lambda code: called.setdefault("exit", code))
    setup_qbittorrent.authenticate()
    assert called["exit"] == 1

def test_update_credentials_success(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.username = None
            self.password = None
            self.logged_in = False
            self.set_prefs = []
        def set_preferences(self, prefs):
            self.set_prefs.append(prefs)
            return True
        def login(self):
            return True
    client = DummyClient()
    setup_qbittorrent.update_credentials(client, "u", "p")
    assert client.username == "u"
    assert client.password == "p"
    assert client.logged_in is False
    assert any("web_ui_username" in d or "web_ui_password" in d for d in client.set_prefs)

def test_update_credentials_fail_update(monkeypatch):
    class DummyClient:
        def set_preferences(self, prefs):
            return False
    client = DummyClient()
    called = {}
    monkeypatch.setattr(sys, "exit", lambda code: called.setdefault("exit", code))
    setup_qbittorrent.update_credentials(client, "u", "p")
    assert called["exit"] == 1

def test_update_credentials_fail_login(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.username = None
            self.password = None
            self.logged_in = False
        def set_preferences(self, prefs):
            return True
        def login(self):
            return False
    client = DummyClient()
    called = {}
    monkeypatch.setattr(sys, "exit", lambda code: called.setdefault("exit", code))
    setup_qbittorrent.update_credentials(client, "u", "p")
    assert called["exit"] == 1

def test_update_credentials_exception(monkeypatch):
    class DummyClient:
        def set_preferences(self, prefs):
            raise Exception("fail")
    client = DummyClient()
    called = {}
    monkeypatch.setattr(sys, "exit", lambda code: called.setdefault("exit", code))
    setup_qbittorrent.update_credentials(client, "u", "p")
    assert called["exit"] == 1

def test_configure_preferences_success(monkeypatch):
    class DummyClient:
        def set_preferences(self, prefs):
            self.prefs = prefs
            return True
    client = DummyClient()
    monkeypatch.setattr(setup_qbittorrent, "QBIT_CONFIG", {"preferences": {"a": 1, "web_ui_username": "x", "web_ui_password": "y"}})
    setup_qbittorrent.configure_preferences(client)
    assert client.prefs == {"a": 1}

def test_configure_preferences_no_prefs(monkeypatch):
    class DummyClient:
        def set_preferences(self, prefs):
            raise AssertionError("Should not be called")
    client = DummyClient()
    monkeypatch.setattr(setup_qbittorrent, "QBIT_CONFIG", {})
    setup_qbittorrent.configure_preferences(client)
