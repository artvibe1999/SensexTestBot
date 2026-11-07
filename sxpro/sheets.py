"""Google Sheet logging, either with a service-account key through the Sheets API
(GOOGLE_SHEET_ID + GOOGLE_SERVICE_ACCOUNT_JSON) or through the sheet's Apps Script web
app (SHEETS_WEBHOOK_URL + SHEETS_SECRET). The service account wins when both are set.

Rows are queued in memory and flushed in batches every few seconds, so trading never
waits on Google. Tabs: Orders, Log, Trades, Status (created, with a header row, when
missing). A failed batch is retried; the Apps Script de-duplicates on the batch id, the
Sheets API path does not, so a batch whose reply was lost can appear twice.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import time
import urllib.parse
import uuid
from datetime import datetime

import requests

from .config import IST

log = logging.getLogger(__name__)

HEADERS = {
    "Orders": ["Time (IST)", "Mode", "Strategy variant", "Action", "Instrument", "Side", "Qty",
               "Ref price (LTP)", "Fill price", "Reason"],
    "Log": ["Time (IST)", "Mode", "Level", "Source", "Message"],
    "Trades": ["Exit time (IST)", "Mode", "Strategy variant", "Reason", "Lots", "Gross P&L", "Costs",
               "Net P&L", "Day P&L", "Instrument", "Qty", "Entry time (IST)", "Entry price", "Exit price",
               "Cost source"],
    "Status": ["Time (IST)", "Mode", "Event", "Details"],
}
MAX_QUEUED = 5000


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class SheetsAPI:
    """Minimal Google Sheets API v4 client authenticated with a service-account key."""

    SCOPE = "https://www.googleapis.com/auth/spreadsheets"
    BASE = "https://sheets.googleapis.com/v4/spreadsheets/"

    def __init__(self, sheet_id: str, sa_json: str):
        info = json.loads(sa_json)
        self.sheet_id = sheet_id
        self.email = info["client_email"]
        self.token_uri = info.get("token_uri") or "https://oauth2.googleapis.com/token"
        self._key_pem = info["private_key"].encode()
        self._key_id = info.get("private_key_id", "")
        self._token, self._token_exp = "", 0.0
        self._ready_tabs: set[str] = set()

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_exp - 120:
            return self._token
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT", "kid": self._key_id}
        claims = {"iss": self.email, "scope": self.SCOPE, "aud": self.token_uri, "iat": now, "exp": now + 3600}
        signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(claims).encode())}"
        key = serialization.load_pem_private_key(self._key_pem, password=None)
        sig = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        r = requests.post(self.token_uri, timeout=30, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": f"{signing_input}.{_b64url(sig)}"})
        if r.status_code != 200:
            raise RuntimeError(f"token: HTTP {r.status_code} {r.text[:200]}")
        body = r.json()
        self._token, self._token_exp = body["access_token"], time.time() + float(body.get("expires_in", 3600))
        return self._token

    def _call(self, method: str, path: str, **kw) -> dict:
        r = requests.request(method, self.BASE + self.sheet_id + path, timeout=60,
                             headers={"Authorization": f"Bearer {self._access_token()}"}, **kw)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    @staticmethod
    def _range(tab: str, cells: str) -> str:
        return urllib.parse.quote(f"'{tab}'!{cells}", safe="")

    def _ensure_tab(self, tab: str, header: list[str]) -> None:
        if tab in self._ready_tabs:
            return
        meta = self._call("GET", "", params={"fields": "sheets.properties.title"})
        if tab not in {s["properties"]["title"] for s in meta.get("sheets", [])}:
            self._call("POST", ":batchUpdate", json={"requests": [{"addSheet": {"properties": {"title": tab}}}]})
        if not self._call("GET", "/values/" + self._range(tab, "A1:A1")).get("values"):
            self._call("PUT", "/values/" + self._range(tab, "A1"), params={"valueInputOption": "RAW"},
                       json={"values": [header]})
        self._ready_tabs.add(tab)

    def append(self, tab: str, header: list[str], rows: list[list]) -> None:
        self._ensure_tab(tab, header)
        self._call("POST", "/values/" + self._range(tab, "A1") + ":append",
                   params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                   json={"values": rows})


def ts(dt: datetime | None = None) -> str:
    return (dt or datetime.now(IST)).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


class SheetLogger:
    def __init__(self, url: str, secret: str, sheet_id: str = "", sa_json: str = ""):
        self.url, self.secret = url, secret
        self.last_error = ""
        self.api: SheetsAPI | None = None
        if sheet_id and sa_json:
            try:
                self.api = SheetsAPI(sheet_id, sa_json)
            except Exception as exc:
                self.last_error = f"service account: {exc}"
                log.error("Google service account unusable: %s", exc)
        self.backend = "service_account" if self.api else "webhook" if url and secret else ""
        self.enabled = bool(self.backend)
        self._lock = threading.Lock()
        self._queue: dict[str, list[list]] = {t: [] for t in HEADERS}
        self._pending: dict[str, tuple[str, list[list]]] = {}  # tab -> (batch id, rows) awaiting ack

    # ---------------- producers (thread-safe, never raise) ----------------
    def add(self, tab: str, row: list) -> None:
        if not self.enabled:
            return
        with self._lock:
            q = self._queue[tab]
            q.append(["" if v is None else v for v in row])
            if len(q) > MAX_QUEUED:
                del q[: len(q) - MAX_QUEUED]

    def order(self, mode, strategy, action, symbol, side, qty, ref, fill, reason, when=None):
        self.add("Orders", [ts(when), mode, strategy, action, symbol, side, qty,
                            round(ref, 2) if ref else "", round(fill, 2) if fill else "", reason])

    def log(self, mode, level, source, message, when=None):
        self.add("Log", [ts(when), mode, level, source, message[:45000]])

    def status(self, mode, event, details, when=None):
        self.add("Status", [ts(when), mode, event, details[:45000]])

    def trade(self, row: list) -> None:
        self.add("Trades", row)

    def stats(self) -> dict:
        with self._lock:
            return {"enabled": self.enabled, "backend": self.backend, "queued": {t: len(q) for t, q in self._queue.items() if q},
                    "pending": {t: len(p[1]) for t, p in self._pending.items()}, "last_error": self.last_error}

    # ---------------- flusher ----------------
    def _post(self, tab: str, batch_id: str, rows: list[list]) -> bool:
        if self.api:
            self.api.append(tab, HEADERS[tab], rows)
            self.last_error = ""
            return True
        body = {"secret": self.secret, "id": batch_id, "tab": tab, "header": HEADERS[tab], "rows": rows}
        r = requests.post(self.url, json=body, timeout=60)
        ok = r.status_code == 200 and r.text.strip() == "ok"
        if not ok:
            self.last_error = f"{tab}: HTTP {r.status_code} {r.text[:120]}"
        return ok

    def flush(self) -> None:
        """Send everything queued (blocking). Called from a worker thread."""
        if not self.enabled:
            return
        for tab in HEADERS:
            with self._lock:
                if tab not in self._pending and self._queue[tab]:
                    self._pending[tab] = (uuid.uuid4().hex, self._queue[tab][:500])
                    del self._queue[tab][:500]
                pending = self._pending.get(tab)
            if not pending:
                continue
            try:
                if self._post(tab, *pending):
                    with self._lock:
                        self._pending.pop(tab, None)
            except Exception as exc:
                self.last_error = f"{tab}: {exc}"

    async def run(self, interval: float = 5.0) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await asyncio.to_thread(self.flush)
            except Exception as exc:  # pragma: no cover
                self.last_error = str(exc)


class SheetLogHandler(logging.Handler):
    """Mirror WARNING+ log records to the sheet's Log tab."""

    def __init__(self, sheet: SheetLogger, mode_fn):
        super().__init__(level=logging.WARNING)
        self.sheet, self.mode_fn = sheet, mode_fn

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(("sxpro.sheets", "urllib3", "httpx")):
            return
        try:
            msg = record.getMessage()
            if record.exc_info:
                msg += " | " + logging.Formatter().formatException(record.exc_info).splitlines()[-1]
            self.sheet.log(self.mode_fn(), record.levelname, record.name, msg)
        except Exception:
            pass
