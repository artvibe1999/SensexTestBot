"""Kite WebSocket (KiteTicker, MODE_FULL) for the opening premium-spike detector only.

Started at 09:13 when SENSEX_SPIKE_22 is armed, for the nearest-expiry strikes around ATM
plus the SENSEX index, and stopped after the 09:30 window. Each tick batch goes straight to
SpikeDetector.on_ticks in the WebSocket thread. The REST quote path used by the rest of the
engine is unchanged.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)


class SpikeFeed:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._ws = None
        self._token: Optional[str] = None
        self._tokens: list[int] = []

    @property
    def running(self) -> bool:
        return self._ws is not None

    def start(self, access_token: Optional[str], tokens: list[int], on_ticks: Callable[[list], None]) -> None:
        if not access_token or not self.api_key or not tokens:
            return
        if self._ws is not None and self._token == access_token:
            return
        self.stop()
        from kiteconnect import KiteTicker   # lazy: twisted is heavy and tests don't need it
        ws = KiteTicker(self.api_key, access_token, reconnect=True)
        self._tokens = sorted({int(t) for t in tokens})

        def _connect(w, _resp):
            w.subscribe(self._tokens)
            w.set_mode(w.MODE_FULL, self._tokens)
            log.info("spike feed connected: %d instruments", len(self._tokens))

        def _ticks(_w, ticks):
            try:
                on_ticks(ticks)
            except Exception:
                log.exception("spike tick handler failed")

        ws.on_connect = _connect
        ws.on_ticks = _ticks
        ws.on_error = lambda _w, code, reason: log.warning("spike feed error %s: %s", code, reason)
        ws.connect(threaded=True)
        self._ws, self._token = ws, access_token

    def stop(self) -> None:
        ws, self._ws, self._token = self._ws, None, None
        if ws is None:
            return
        try:
            from twisted.internet import reactor
            ws.stop_retry()
            reactor.callFromThread(ws.close)
            log.info("spike feed stopped")
        except Exception as exc:
            log.info("spike feed close: %s", exc)
