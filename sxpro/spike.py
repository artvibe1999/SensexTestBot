"""Tick-driven opening premium-spike detector (strategy SENSEX_SPIKE_22).

Runs inside the WebSocket thread on every streamed tick, so the per-tick work is a few dict
lookups and an O(1) amortised monotonic-deque update. When a near-ATM option's mid price
rises `spike_pct` above its lowest mid of the last `window_s` seconds (with a tight spread)
inside the opening window, it fires once per day and hands a SpikeTrigger to the engine's
event loop. Study and parameters: docs/OPENING-SPIKE-2026-11.md (ported from sensex-pro-bot).
"""
from __future__ import annotations

import logging
import threading
import time as _time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Callable, Optional

from .config import IST

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpikeContract:
    token: int
    symbol: str
    strike: float
    option_type: str      # CE / PE
    expiry: date
    lot_size: int
    tick_size: float


@dataclass(frozen=True)
class SpikeTrigger:
    contract: SpikeContract
    detected_at: datetime
    mid: float
    low: float
    bid: float
    ask: float
    spot: float

    @property
    def rise(self) -> float:
        return self.mid / self.low - 1


class SpikeDetector:
    def __init__(self, spike_pct: float = 0.08, window_s: float = 10.0, start: time = time(9, 15, 20),
                 end: time = time(9, 30), max_spread_pct: float = 0.008, near_points: float = 150.0,
                 clock: Callable[[], datetime] = lambda: datetime.now(IST),
                 mono: Callable[[], float] = _time.monotonic):
        self.spike_pct, self.window_s = spike_pct, window_s
        self.start, self.end = start, end
        self.max_spread_pct, self.near_points = max_spread_pct, near_points
        self.clock, self.mono = clock, mono
        self.enabled = False
        self.on_trigger: Optional[Callable[[SpikeTrigger], None]] = None
        self._lock = threading.Lock()
        self._day: Optional[date] = None
        self._fired: Optional[date] = None
        self._contracts: dict[int, SpikeContract] = {}
        self._index_token: Optional[int] = None
        self._spot = 0.0
        self._first: dict[int, float] = {}               # token -> first tick time (monotonic)
        self._mins: dict[int, deque] = {}                # token -> monotonic deque of (t, mid)

    # ------------------------------------------------------------ setup (engine thread)
    def configure_day(self, day: date, contracts: list[SpikeContract], index_token: int) -> None:
        with self._lock:
            if self._day == day and self._contracts:
                return
            self._day = day
            self._contracts = {c.token: c for c in contracts}
            self._index_token = int(index_token)
            self._first.clear()
            self._mins.clear()
            self._spot = 0.0
        log.info("spike detector armed for %s: %d contracts", day, len(contracts))

    @property
    def fired_today(self) -> bool:
        return self._fired is not None and self._fired == self.clock().date()

    # ------------------------------------------------------------ hot path (WebSocket thread)
    def on_ticks(self, ticks: list[dict]) -> None:
        if not self.enabled or not self._contracts:
            return
        now = self.clock()
        t = now.time()
        if self._day != now.date() or self._fired == self._day or t > self.end:
            return
        mono = self.mono()
        trigger = None
        with self._lock:
            for tk in ticks:
                token = tk.get("instrument_token")
                if token == self._index_token:
                    lp = tk.get("last_price") or 0.0
                    if lp > 0:
                        self._spot = float(lp)
                    continue
                c = self._contracts.get(token)
                if c is None:
                    continue
                depth = tk.get("depth") or {}
                bid = _best(depth.get("buy"))
                ask = _best(depth.get("sell"))
                if bid <= 0 or ask <= 0:
                    continue
                mid = (bid + ask) / 2
                dq = self._mins.setdefault(token, deque())
                self._first.setdefault(token, mono)
                while dq and dq[-1][1] >= mid:      # monotonic deque: increasing mids
                    dq.pop()
                dq.append((mono, mid))
                while dq and dq[0][0] < mono - self.window_s:
                    dq.popleft()
                if trigger is not None or t < self.start or mono - self._first[token] < self.window_s:
                    continue
                low = dq[0][1]
                if low <= 0 or mid / low - 1 < self.spike_pct:
                    continue
                if (ask - bid) / mid > self.max_spread_pct:
                    continue
                if self._spot <= 0 or abs(c.strike - self._spot) > self.near_points:
                    continue
                trigger = SpikeTrigger(c, now, mid, low, bid, ask, self._spot)
            if trigger is not None:
                self._fired = self._day
        if trigger is not None:
            log.info("premium spike: %s %+.1f%% in %.0fs (bid %.2f ask %.2f, SENSEX %.0f)",
                     trigger.contract.symbol, trigger.rise * 100, self.window_s, trigger.bid, trigger.ask,
                     trigger.spot)
            cb = self.on_trigger
            if cb is not None:
                try:
                    cb(trigger)
                except Exception:
                    log.exception("spike callback failed")


def _best(levels) -> float:
    for lvl in levels or []:
        if (lvl.get("price") or 0) > 0 and (lvl.get("quantity") or 0) > 0:
            return float(lvl["price"])
    return 0.0
