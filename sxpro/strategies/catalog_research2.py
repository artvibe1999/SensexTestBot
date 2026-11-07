"""Research strategies 66-79: second and third 4-year entry screens (scripts/screen2.py,
scripts/screen3.py; train Sep 2022 - Oct 2025, holdout Nov 2025 - Nov 2026). Each rule
here was profitable in both periods for most of its parameter grid, not just one setting.

Like 61-65 they buy an at-the-money weekly option and hold until the rule's exit or 15:20.
"""
from __future__ import annotations

from datetime import time
from typing import Optional

import numpy as np

from .base import BREAKOUT, CE, PE, Signal, sign
from .catalog_research import Research


def bands(ctx, k: float) -> Optional[tuple[float, float]]:
    """Noise band for the last closed candle: open/prev-close x (1 +/- k x sigma)."""
    sigma = ctx.aux.get("noise")
    slot = ctx.n_today - 1
    if sigma is None or slot < 0 or slot >= len(sigma) or np.isnan(sigma[slot]):
        return None
    day_open = float(ctx.today["open"].iloc[0])
    return (max(day_open, ctx.pdc) * (1 + k * sigma[slot]), min(day_open, ctx.pdc) * (1 - k * sigma[slot]))


def at(ctx, hh: int, mm: int) -> bool:
    return ctx.close_time == time(hh, mm)


class VwapExit:
    """Exit on a 5-min close across VWAP."""

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed across VWAP" if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0 else None


class NewExtreme66(VwapExit, Research):
    sid, name = "SENSEX_HLBRK_66", "New Day High/Low Beyond Noise Band"
    start, end = time(11, 0), time(14, 30)
    needs = ("noise",)
    k = 1.0

    def entry(self, ctx):
        b = bands(ctx, self.k)
        if b is None or ctx.n_today < 3:
            return None
        ub, lb = b
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        prior = ctx.today.iloc[:-1]
        if price > float(prior["high"].max()) and price > ub and price > vw:
            return Signal(CE, sl_price=vw, note=f"new day high beyond noise {ub:.0f}")
        if price < float(prior["low"].min()) and price < lb and price < vw:
            return Signal(PE, sl_price=vw, note=f"new day low beyond noise {lb:.0f}")
        return None


class Midday67(Research):
    sid, name = "SENSEX_MIDDAY_67", "11:00 Noise-Band Momentum"
    start = end = time(11, 0)
    needs = ("noise",)
    k = 0.75

    def entry(self, ctx):
        b = bands(ctx, self.k)
        if b is None:
            return None
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        if price > b[0] and price > vw:
            return Signal(CE, note=f"{ctx.close_time:%H:%M} above noise band {b[0]:.0f}")
        if price < b[1] and price < vw:
            return Signal(PE, note=f"{ctx.close_time:%H:%M} below noise band {b[1]:.0f}")
        return None


class Midday68(Midday67):
    sid, name = "SENSEX_MIDDAY_68", "12:30 Noise-Band Momentum"
    start = end = time(12, 30)


class OpenDrive69(Research):
    sid, name = "SENSEX_ODRIVE_69", "Opening Drive (30 min)"
    start = end = time(9, 45)
    trail_mult = 3.0
    thr = 0.2

    def entry(self, ctx):
        r = ctx.today.iloc[:6]
        if len(r) < 6:
            return None
        hi, lo = float(r["high"].max()), float(r["low"].min())
        mv = float(r["close"].iloc[-1]) - float(r["open"].iloc[0])
        if hi <= lo or abs(mv) < self.thr * (ctx.pdh - ctx.pdl):
            return None
        pos = (float(r["close"].iloc[-1]) - lo) / (hi - lo)
        if mv > 0 and pos >= 0.75:
            return Signal(CE, sl_price=lo, note=f"opening drive +{mv:.0f} pts")
        if mv < 0 and pos <= 0.25:
            return Signal(PE, sl_price=hi, note=f"opening drive {mv:.0f} pts")
        return None


class VwapPullback70(Research):
    sid, name = "SENSEX_VWAPPB_70", "Trend-Day Pullback to VWAP"
    start, end = time(9, 50), time(13, 0)
    needs = ("noise",)
    trail_mult = 3.0
    k, tol, stop_atr = 0.75, 0.5, 1.0

    def entry(self, ctx):
        sigma = ctx.aux.get("noise")
        t = ctx.today
        if sigma is None or len(t) < 8:
            return None
        day_open = float(t["open"].iloc[0])
        up_ref, dn_ref = max(day_open, ctx.pdc), min(day_open, ctx.pdc)
        atr = float(ctx.last["atr"])
        trend, touched = 0, False
        for j in range(5, len(t)):       # 09:45 candle close onwards (slot 5 closes 09:45)
            row = t.iloc[j]
            s = sigma[j] if j < len(sigma) else np.nan
            if np.isnan(s):
                return None
            c, vw = float(row["close"]), float(row["vwap"])
            if trend == 0:
                if c > up_ref * (1 + self.k * s) and c > vw:
                    trend = 1
                elif c < dn_ref * (1 - self.k * s) and c < vw:
                    trend = -1
                continue
            last = j == len(t) - 1
            if (trend > 0 and row["low"] <= vw + self.tol * atr) or (trend < 0 and row["high"] >= vw - self.tol * atr):
                touched = True
            if touched and trend * (c - vw) > 0 and trend * (c - float(t["close"].iloc[j - 1])) > 0:
                if not last:
                    return None      # the setup fired on an earlier candle
                d = CE if trend > 0 else PE
                return Signal(d, sl_price=vw - trend * self.stop_atr * atr, note="pullback to VWAP on a trend day")
            if trend * (c - vw) < -2 * atr:
                return None
        return None


class InsideDayBreak71(Research):
    sid, name = "SENSEX_INSIDE_71", "Inside-Day Range Breakout"
    category = BREAKOUT
    start, end = time(9, 30), time(14, 0)
    needs = ("daily",)
    buf = 0.1

    def entry(self, ctx):
        d = ctx.aux.get("daily")
        if d is None or len(d) < 2:
            return None
        y, yy = d.iloc[-1], d.iloc[-2]
        if not (y["high"] <= yy["high"] and y["low"] >= yy["low"]):
            return None
        rng = ctx.pdh - ctx.pdl
        price = float(ctx.last["close"])
        if price > ctx.pdh:
            return Signal(CE, sl_price=ctx.pdh - self.buf * rng, note=f"inside day, broke PDH {ctx.pdh:.0f}")
        if price < ctx.pdl:
            return Signal(PE, sl_price=ctx.pdl + self.buf * rng, note=f"inside day, broke PDL {ctx.pdl:.0f}")
        return None


class Thrust72(Research):
    sid, name = "SENSEX_THRUST_72", "Thrust Candle Beyond Noise Band"
    start, end = time(9, 45), time(14, 30)
    needs = ("noise",)
    trail_mult = 3.0
    m, k = 1.5, 0.5

    def entry(self, ctx):
        b = bands(ctx, self.k)
        if b is None:
            return None
        c = ctx.last
        hi, lo, price, atr = float(c["high"]), float(c["low"]), float(c["close"]), float(c["atr"])
        if atr <= 0 or hi - lo < self.m * atr:
            return None
        pos = (price - lo) / (hi - lo)
        if pos >= 0.8 and price > b[0] and price > c["vwap"]:
            return Signal(CE, sl_price=lo, note=f"thrust candle {hi - lo:.0f} pts")
        if pos <= 0.2 and price < b[1] and price < c["vwap"]:
            return Signal(PE, sl_price=hi, note=f"thrust candle {hi - lo:.0f} pts")
        return None


class LunchBreak73(Research):
    sid, name = "SENSEX_LUNCH_73", "12:00-13:00 Range Break With the Day"
    category = BREAKOUT
    start, end = time(13, 5), time(14, 45)
    min_move = 0.003

    def entry(self, ctx):
        t = ctx.today
        lunch = t[(t.index.time >= time(12, 0)) & (t.index.time < time(13, 0))]
        if len(lunch) < 12:
            return None
        hi, lo = float(lunch["high"].max()), float(lunch["low"].min())
        day_open = float(t["open"].iloc[0])
        mv = float(lunch["close"].iloc[-1]) / day_open - 1
        if abs(mv) < self.min_move:
            return None
        price = float(ctx.last["close"])
        if mv > 0 and price > hi:
            return Signal(CE, sl_price=lo, note=f"broke lunch range high {hi:.0f}")
        if mv < 0 and price < lo:
            return Signal(PE, sl_price=hi, note=f"broke lunch range low {lo:.0f}")
        return None


class Orb60_74(Research):
    sid, name = "SENSEX_ORB60_74", "60-min Opening Range Breakout"
    category = BREAKOUT
    start, end = time(10, 20), time(13, 30)

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 13:
            return None
        r = t.iloc[:12]
        hi, lo = float(r["high"].max()), float(r["low"].min())
        price = float(ctx.last["close"])
        if price > hi:
            return Signal(CE, sl_price=lo, note=f"60-min range {lo:.0f}-{hi:.0f} up-break")
        if price < lo:
            return Signal(PE, sl_price=hi, note=f"60-min range {lo:.0f}-{hi:.0f} down-break")
        return None


class ThreeDayBreak75(Research):
    sid, name = "SENSEX_3DAY_75", "3-Day High/Low Breakout"
    category = BREAKOUT
    start, end = time(9, 30), time(14, 0)
    needs = ("daily",)
    trail_mult = 3.0
    n = 3

    def entry(self, ctx):
        d = ctx.aux.get("daily")
        if d is None or len(d) < self.n:
            return None
        hi, lo = float(d["high"].iloc[-self.n:].max()), float(d["low"].iloc[-self.n:].min())
        day_open = float(ctx.today["open"].iloc[0])
        if not (lo < day_open < hi):
            return None
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        if price > hi and price > vw:
            return Signal(CE, sl_price=ctx.pdh if ctx.pdh < price else vw, note=f"broke 3-day high {hi:.0f}")
        if price < lo and price < vw:
            return Signal(PE, sl_price=ctx.pdl if ctx.pdl > price else vw, note=f"broke 3-day low {lo:.0f}")
        return None


class CloseStrength76(Research):
    sid, name = "SENSEX_CLOSESTR_76", "Strong Close Follow-Through"
    start = end = time(9, 45)
    trail_mult = 3.0
    buf = 0.002

    def entry(self, ctx):
        rng = ctx.pdh - ctx.pdl
        if rng <= 0:
            return None
        pos = (ctx.pdc - ctx.pdl) / rng
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        low, high = float(ctx.today["low"].min()), float(ctx.today["high"].max())
        if pos >= 0.8 and price > ctx.pdc * (1 + self.buf) and price > vw:
            return Signal(CE, sl_price=min(low, ctx.pdc), note="yesterday closed strong, holding above")
        if pos <= 0.2 and price < ctx.pdc * (1 - self.buf) and price < vw:
            return Signal(PE, sl_price=max(high, ctx.pdc), note="yesterday closed weak, holding below")
        return None


class First30_77(Research):
    sid, name = "SENSEX_FIRST30_77", "First-30-Minute Direction"
    start = end = time(9, 45)
    thr = 0.002

    def entry(self, ctx):
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        r = price / ctx.pdc - 1
        if r >= self.thr and price > vw:
            return Signal(CE, note=f"first 30 min {r:+.2%} vs prev close")
        if r <= -self.thr and price < vw:
            return Signal(PE, note=f"first 30 min {r:+.2%} vs prev close")
        return None


class NoiseVwap78(VwapExit, Research):
    sid, name = "SENSEX_NOISEV_78", "Noise-Area Momentum, VWAP Exit"
    start, end = time(9, 45), time(14, 15)
    needs = ("noise",)
    k = 1.0

    def entry(self, ctx):
        t = ctx.close_time
        if (t.hour * 60 + t.minute - (9 * 60 + 45)) % 30 != 0:
            return None
        b = bands(ctx, self.k)
        if b is None:
            return None
        c = ctx.last
        price, vw = float(c["close"]), float(c["vwap"])
        if price > b[0] and price > vw:
            return Signal(CE, note=f"above noise band {b[0]:.0f}")
        if price < b[1] and price < vw:
            return Signal(PE, note=f"below noise band {b[1]:.0f}")
        return None


class VolBreakLate79(Research):
    sid, name = "SENSEX_VBOL_79", "Open +/- 0.35 x Range Breakout (to 14:00)"
    start, end = time(9, 25), time(14, 0)
    trail_mult = 3.0
    k = 0.35

    def entry(self, ctx):
        rng = ctx.pdh - ctx.pdl
        day_open = float(ctx.today["open"].iloc[0])
        up, dn = day_open + self.k * rng, day_open - self.k * rng
        price = float(ctx.last["close"])
        if price > up:
            return Signal(CE, sl_price=dn, note=f"open + 0.35 x range {rng:.0f}")
        if price < dn:
            return Signal(PE, sl_price=up, note=f"open - 0.35 x range {rng:.0f}")
        return None


STRATEGIES_66_79 = [NewExtreme66(), Midday67(), Midday68(), OpenDrive69(), VwapPullback70(), InsideDayBreak71(),
                    Thrust72(), LunchBreak73(), Orb60_74(), ThreeDayBreak75(), CloseStrength76(), First30_77(),
                    NoiseVwap78(), VolBreakLate79()]
