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
    max_entries: int = 99                # entries per day (re-entry "yes, once" = 2)
    needs: tuple = ()                    # extra feeds in ctx.aux: vix, nifty, breadth, oi, first_min, daily
    tune: dict = {}                      # backtest-derived adjustments, see apply_tuning / strategies/tuning.py

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

    def apply_tuning(self, ctx: MarketContext, sig: Signal) -> Optional[Signal]:
        """Apply this strategy's `tune` adjustments to a raw signal (None = filtered out).

        Keys: side "CE"|"PE"; start/end "HH:MM" (entry window); trend15 True (15-min
        9/21 EMA must agree with the direction); adx_min / adx_max (5-min ADX bounds);
        min_stop_atr k (stop at least k x ATR(14) from entry); rr k (target = k x risk);
        no_target True; book f (book fraction f at target, trail the rest);
        prem_sl p (premium stop -p); max_hold minutes (applied by the engine).
        """
        t = self.tune
        if not t:
            return sig
        c = ctx.last
        price = float(c["close"])
        if t.get("side") and sig.direction != t["side"]:
            return None
        ct = ctx.close_time
        if t.get("start") and ct < time.fromisoformat(t["start"]):
            return None
        if t.get("end") and ct > time.fromisoformat(t["end"]):
            return None
        if t.get("adx_min") is not None and not (c["adx"] >= t["adx_min"]):
            return None
        if t.get("adx_max") is not None and not (c["adx"] <= t["adx_max"]):
            return None
        if t.get("trend15"):
            l15 = ctx.df15.iloc[-1] if ctx.df15 is not None and len(ctx.df15) else None
            if l15 is None or sign(sig.direction) * (l15["ema9"] - l15["ema21"]) <= 0:
                return None
        d = sign(sig.direction)
        stop = sig.sl_price if sig.sl_price is not None else sig.sl_close
        if t.get("min_stop_atr") and stop is not None and c["atr"] > 0:
            want = price - d * t["min_stop_atr"] * float(c["atr"])
            if d * (price - stop) < d * (price - want):
                stop = want
                if sig.sl_price is not None:
                    sig.sl_price = stop
                else:
                    sig.sl_close = stop
                    if "sl_close" in sig.meta:
                        sig.meta["sl_close"] = stop
        if t.get("no_target"):
            sig.target = None
        elif t.get("rr") and stop is not None and d * (price - stop) > 0:
            sig.target = price + d * t["rr"] * abs(price - stop)
        if t.get("book") is not None:
            sig.book_fraction = float(t["book"])
        if t.get("prem_sl") is not None:
            sig.prem_sl_pct = float(t["prem_sl"])
        sig.note = (sig.note + " | tuned").strip()
        return sig

    def describe(self) -> str:
        return (f"{self.sid} – {self.name} [{self.category}] {self.start:%H:%M}-{self.end:%H:%M} "
                f"Δ{self.delta_target:.2f} ₹{self.prem_min:.0f}-{self.prem_max:.0f}")
