"""Service-account Sheets API backend (Google calls mocked)."""
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes

from sxpro import sheets
from sxpro.sheets import HEADERS, SheetLogger

import base64


def _sa():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, json.dumps({"type": "service_account", "client_email": "bot@p.iam.gserviceaccount.com",
                            "private_key": pem, "private_key_id": "k1",
                            "token_uri": "https://oauth2.googleapis.com/token"})


class _Resp:
    def __init__(self, body, status=200):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


def test_service_account_creates_tab_header_and_appends(monkeypatch):
    key, sa = _sa()
    calls = []

    def fake_post(url, data=None, timeout=None, **kw):
        assert url == "https://oauth2.googleapis.com/token"
        head, claims, sig = data["assertion"].split(".")
        pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        key.public_key().verify(pad(sig), f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
        c = json.loads(pad(claims))
        assert c["iss"] == "bot@p.iam.gserviceaccount.com" and "spreadsheets" in c["scope"]
        calls.append(("TOKEN",))
        return _Resp({"access_token": "tok", "expires_in": 3600})

    def fake_request(method, url, headers=None, timeout=None, params=None, json=None):
        assert headers["Authorization"] == "Bearer tok"
        calls.append((method, url.split("/spreadsheets/SID")[1], json))
        if method == "GET" and url.endswith("SID"):
            return _Resp({"sheets": [{"properties": {"title": "Old_Tab"}}]})
        if method == "GET":
            return _Resp({})  # empty tab
        return _Resp({})

    monkeypatch.setattr(sheets.requests, "post", fake_post)
    monkeypatch.setattr(sheets.requests, "request", fake_request)
    sl = SheetLogger("", "", "SID", sa)
    assert sl.enabled and sl.backend == "service_account"
    sl.status("paper", "start", "hello")
    sl.status("paper", "beat", "again")
    sl.flush()
    assert sl.stats()["pending"] == {} and sl.last_error == ""
    methods = [c[0] for c in calls]
    assert methods.count("TOKEN") == 1
    add = [c for c in calls if c[0] == "POST" and c[1] == ":batchUpdate"][0]
    assert add[2]["requests"][0]["addSheet"]["properties"]["title"] == "Status"
    header = [c for c in calls if c[0] == "PUT"][0]
    assert header[2] == {"values": [HEADERS["Status"]]}
    append = [c for c in calls if c[0] == "POST" and c[1].endswith(":append")][0]
    assert [r[2] for r in append[2]["values"]] == ["start", "beat"]
    # second flush: tab already prepared, token reused -> only the append
    calls.clear()
    sl.status("paper", "x", "y")
    sl.flush()
    assert [c[0] for c in calls] == ["POST"]


def test_failed_append_is_retried(monkeypatch):
    _, sa = _sa()
    monkeypatch.setattr(sheets.requests, "post", lambda *a, **k: _Resp({"access_token": "tok"}))
    state = {"fail": True}

    def fake_request(method, url, **kw):
        if url.endswith(":append") and state["fail"]:
            return _Resp({"error": "quota"}, 429)
        if method == "GET" and url.endswith("SID"):
            return _Resp({"sheets": [{"properties": {"title": "Log"}}]})
        return _Resp({"values": [["h"]]} if method == "GET" else {})

    monkeypatch.setattr(sheets.requests, "request", fake_request)
    sl = SheetLogger("", "", "SID", sa)
    sl.log("paper", "WARNING", "x", "m")
    sl.flush()
    assert "429" in sl.last_error and sl.stats()["pending"] == {"Log": 1}
    state["fail"] = False
    sl.flush()
    assert sl.stats()["pending"] == {} and sl.last_error == ""


def test_bad_key_disables_sheet_logging():
    sl = SheetLogger("", "", "SID", "not json")
    assert not sl.enabled and "service account" in sl.last_error
