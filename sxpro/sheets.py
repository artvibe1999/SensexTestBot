"""Google Sheet logging through the sheet's Apps Script web app (SHEETS_WEBHOOK_URL).

Rows are queued in memory and flushed in batches every few seconds, so trading never
waits on Google. Tabs: Orders, Log, Trades, Status. A failed batch is retried with the
same id; the Apps Script de-duplicates on that id.
"""
from __future__ import annotations

import asyncio
import logging
import threading
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


def ts(dt: datetime | None = None) -> str:
    return (dt or datetime.now(IST)).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


class SheetLogger:
    def __init__(self, url: str, secret: str):
        self.url, self.secret = url, secret
        self.enabled = bool(url and secret)
        self._lock = threading.Lock()
        self._queue: dict[str, list[list]] = {t: [] for t in HEADERS}
        self._pending: dict[str, tuple[str, list[list]]] = {}  # tab -> (batch id, rows) awaiting ack
        self.last_error = ""

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
            return {"enabled": self.enabled, "queued": {t: len(q) for t, q in self._queue.items() if q},
                    "pending": {t: len(p[1]) for t, p in self._pending.items()}, "last_error": self.last_error}

    # ---------------- flusher ----------------
    def _post(self, tab: str, batch_id: str, rows: list[list]) -> bool:
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
