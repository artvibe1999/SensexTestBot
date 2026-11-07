"""Strategy interface.

A strategy only looks at closed 5-min SENSEX candles (MarketContext) and returns a
Signal describing direction, underlying stop/target and option preferences. Strike
selection, sizing, risk checks and execution are done by the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Optional

from ..market import BEAR, BULL, SIDEWAYS, MarketContext

CE, PE = "CE", "PE"

TREND, BREAKOUT, REVERSAL = "trend", "breakout", "reversal"


def sign(direction: str) -> int:
    return 1 if direction == CE else -1


@dataclass
class Signal:
    direction: str                       # CE / PE
    sl_price: Optional[float] = None     # underlying price stop (checked on every tick)
    sl_close: Optional[float] = None     # underlying close-based stop (checked on candle close)
    target: Optional[float] = None       # underlying target for profit booking
    book_fraction: float = 1.0           # share of qty booked at target (rest trails)
    prem_sl_pct: Optional[float] = None  # option-premium stop, e.g. 0.15 => -15%
    prem_target_pct: Optional[float] = None
    setup_key: str = ""
    note: str = ""
    meta: dict = field(default_factory=dict)


class Strategy:
    sid: str = ""
    name: str = ""
    category: str = TREND
    start: time = time(9, 20)
    end: time = time(15, 10)
    time_exit: time = time(15, 15)
    max_hold_min: int = 120
    delta_target: float = 0.50
    delta_min: float = 0.40
    delta_max: float = 0.60
    prem_min: float = 200
    prem_max: float = 400
    expiry_rule: str = "weekly"
    capital_pct: float = 0.10
    reentry: str = "no"                  # "no" | "setup" (new setup only) | "yes"
    trail_kind: str = "close"            # "close" | "price" | "none"
    uses_3min: bool = False

    # ---------------------------------------------------------------
    def in_window(self, ctx: MarketContext) -> bool:
        t = ctx.close_time
        return self.start <= t <= self.end

    def entry(self, ctx: MarketContext) -> Optional[Signal]:  # pragma: no cover - abstract
        raise NotImplementedError

    def exit_on_close(self, ctx: MarketContext, pos: dict) -> Optional[str]:
        """Strategy-specific exit condition evaluated on each candle close."""
        return None

    def trail_level(self, ctx: MarketContext, pos: dict) -> Optional[float]:
        """Underlying trailing-stop level (engine only ratchets it in the trade's favour)."""
        return None

    # helpers -----------------------------------------------------------
    @staticmethod
    def rr_target(entry: float, stop: float, rr: float, direction: str) -> Optional[float]:
        risk = abs(entry - stop)
        if risk <= 0:
            return None
        return entry + sign(direction) * rr * risk

    @staticmethod
    def regime_ok(ctx: MarketContext, direction: str, category: str) -> bool:
        """Framework section 2 gating."""
        if ctx.regime == BULL and direction == PE:
            return False
        if ctx.regime == BEAR and direction == CE:
            return False
        if ctx.regime == SIDEWAYS and category == BREAKOUT:
            return False
        return True

    @staticmethod
    def vol_ok(ctx: MarketContext) -> bool:
        """True when the volume proxy (SENSEX futures) is available."""
        return float(ctx.today["volume"].sum()) > 0

    def describe(self) -> str:
        return (f"{self.sid} – {self.name} [{self.category}] {self.start:%H:%M}-{self.end:%H:%M} "
                f"Δ{self.delta_target:.2f} ₹{self.prem_min:.0f}-{self.prem_max:.0f}")
