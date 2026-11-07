"""Research strategies 61-65: entry rules found by scripts/screen.py on 4 years of SENSEX
1-minute data (Sep 2022 - Oct 2025 train, Nov 2025 - Nov 2026 holdout; docs/research_61_65.md).

All are trend-day breakouts that hold an at-the-money weekly option until a trailing exit
or 15:20; they rely on option convexity on days that keep moving, so they take few,
larger trades. They run before strategies 1-60 (priority) because the bot holds one
position at a time.

61 NOISE  - "noise area" intraday momentum (Zarattini, Aziz & Barbon 2024): every 30 min
            from 09:45, enter when price closes outside open x (1 +/- 1.25 x the 14-day
            average move from the open at that time of day) on the VWAP side; hold to 15:20.
62 VBO    - volatility breakout: first 5-min close beyond open +/- 0.7 x previous day's
            range by 12:00; stop at the opposite level; chandelier trail 3 x opening range.
63 LATEMOM- at 14:00, day move from the open beyond +/-0.6% on the VWAP side; hold to 15:20.
64 PDB    - previous-day high/low breakout (open inside yesterday's range) by 12:00; stop
            0.1 x prior range back inside; exit on a 5-min close across VWAP.
65 ORB30  - 30-min opening range break in the direction of the first 30 minutes, by 11:00;
            stop at the other side of the range; chandelier trail 3 x opening range.
"""
from __future__ import annotations

from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from ..market import MarketContext
from .base import BREAKOUT, CE, PE, TREND, Signal, Strategy, sign

NOISE_DAYS = 14


def noise_sigma(df5: pd.DataFrame, today, days: int = NOISE_DAYS) -> Optional[np.ndarray]:
    """Average |close/day-open - 1| per 5-minute slot (0 = 09:15-09:20 candle) over the
    `days` sessions before `today`, from 5-minute candles."""
    past = df5[df5.index.date < today]
    if past.empty:
        return None
    out = []
    for _, g in list(past.groupby(past.index.date))[-days:]:
        slot = ((g.index.hour - 9) * 60 + g.index.minute - 15) // 5
        row = np.full(75, np.nan)
        ok = (slot >= 0) & (slot < 75)
        row[slot[ok]] = np.abs(g["close"].to_numpy()[ok] / float(g["open"].iloc[0]) - 1)
        out.append(row)
    if len(out) < days:
        return None
    return np.nanmean(np.vstack(out), axis=0)


class Research(Strategy):
    category = TREND
    delta_target, delta_min, delta_max = 0.50, 0.42, 0.58
    prem_min, prem_max = 50, 900
    time_exit, max_hold_min = time(15, 20), 330
    trail_kind = "none"
    priority = 10
    trail_mult: Optional[float] = None   # chandelier trail: best extreme - k x opening-range ATR

    def entry_bars(self, ctx, pos) -> pd.DataFrame:
        t = pd.Timestamp(pos["entry_time"])
        return ctx.today[ctx.today.index + pd.Timedelta(minutes=5) > t]

    @staticmethod
    def open_atr(ctx) -> float:
        first = ctx.today.iloc[:6]
        return float((first["high"] - first["low"]).mean()) if len(first) else 0.0

    def exit_on_close(self, ctx, pos):
        if self.trail_mult:
            bars = self.entry_bars(ctx, pos)
            dist = self.trail_mult * self.open_atr(ctx)   # first <= 6 candles of the day, no look-ahead
            if len(bars) and dist > 0:
                c = float(ctx.last["close"])
                if pos["direction"] == CE and c < float(bars["high"].max()) - dist:
                    return f"chandelier trail {dist:.0f} pts"
                if pos["direction"] == PE and c > float(bars["low"].min()) + dist:
                    return f"chandelier trail {dist:.0f} pts"
        return self.exit_rule(ctx, pos)

    def exit_rule(self, ctx, pos):
        return None


class NoiseMomentum61(Research):
    sid, name = "SENSEX_NOISE_61", "Noise-Area Intraday Momentum"
    start, end = time(9, 45), time(14, 15)
    needs = ("noise",)
    k = 1.25

    def entry(self, ctx):
        t = ctx.close_time
        if (t.hour * 60 + t.minute - (9 * 60 + 45)) % 30 != 0:
            return None
        sigma = ctx.aux.get("noise")
        if sigma is None:
            return None
        slot = ctx.n_today - 1
        if slot >= len(sigma) or np.isnan(sigma[slot]):
            return None
        c = ctx.last
        day_open = float(ctx.today["open"].iloc[0])
        ub = max(day_open, ctx.pdc) * (1 + self.k * sigma[slot])
        lb = min(day_open, ctx.pdc) * (1 - self.k * sigma[slot])
        price = float(c["close"])
        if price > ub and price > c["vwap"]:
            return Signal(CE, note=f"above noise band {ub:.0f} (sigma {sigma[slot]:.2%})")
        if price < lb and price < c["vwap"]:
            return Signal(PE, note=f"below noise band {lb:.0f} (sigma {sigma[slot]:.2%})")
        return None


class VolatilityBreakout62(Research):
    sid, name = "SENSEX_VBO_62", "Open +/- 0.7 x Range Breakout"
    start, end = time(9, 25), time(12, 0)
    trail_mult = 3.0
    k = 0.7

    def entry(self, ctx):
        rng = ctx.pdh - ctx.pdl
        day_open = float(ctx.today["open"].iloc[0])
        up, dn = day_open + self.k * rng, day_open - self.k * rng
        price = float(ctx.last["close"])
        if price > up:
            return Signal(CE, sl_price=dn, note=f"open {day_open:.0f} + 0.7 x range {rng:.0f}")
        if price < dn:
            return Signal(PE, sl_price=up, note=f"open {day_open:.0f} - 0.7 x range {rng:.0f}")
        return None


class LateMomentum63(Research):
    sid, name = "SENSEX_LATEMOM_63", "Late-Session Momentum"
    start, end = time(14, 0), time(14, 0)
    thr = 0.006

    def entry(self, ctx):
        c = ctx.last
        price = float(c["close"])
        ret = price / float(ctx.today["open"].iloc[0]) - 1
        if ret > self.thr and price > c["vwap"]:
            return Signal(CE, note=f"day +{ret:.2%} from open at 14:00")
        if ret < -self.thr and price < c["vwap"]:
            return Signal(PE, note=f"day {ret:.2%} from open at 14:00")
        return None


class PrevDayBreakout64(Research):
    sid, name = "SENSEX_PDB_64", "Previous-Day High/Low Breakout"
    start, end = time(9, 30), time(12, 0)
    buf = 0.1

    def entry(self, ctx):
        day_open = float(ctx.today["open"].iloc[0])
        if not (ctx.pdl <= day_open <= ctx.pdh) or ctx.n_today < 2:
            return None
        c, p = ctx.c(0), ctx.c(1)
        rng = ctx.pdh - ctx.pdl
        price = float(c["close"])
        if price > ctx.pdh and p["close"] <= ctx.pdh:
            return Signal(CE, sl_price=ctx.pdh - self.buf * rng, note=f"broke PDH {ctx.pdh:.0f}")
        if price < ctx.pdl and p["close"] >= ctx.pdl:
            return Signal(PE, sl_price=ctx.pdl + self.buf * rng, note=f"broke PDL {ctx.pdl:.0f}")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed across VWAP" if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0 else None


class OpeningRange30_65(Research):
    sid, name = "SENSEX_ORB30_65", "30-min Opening Range, First-Move Direction"
    category = BREAKOUT
    start, end = time(9, 50), time(11, 0)
    trail_mult = 3.0

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 7:
            return None
        rng = t.iloc[:6]
        hi, lo = float(rng["high"].max()), float(rng["low"].min())
        first = np.sign(float(rng["close"].iloc[-1]) - float(rng["open"].iloc[0]))
        price = float(ctx.last["close"])
        if first > 0 and price > hi:
            return Signal(CE, sl_price=lo, note=f"30-min range {lo:.0f}-{hi:.0f} up-break")
        if first < 0 and price < lo:
            return Signal(PE, sl_price=hi, note=f"30-min range {lo:.0f}-{hi:.0f} down-break")
        return None


STRATEGIES_61_65: list[Strategy] = [VolatilityBreakout62(), NoiseMomentum61(), OpeningRange30_65(),
                                    PrevDayBreakout64(), LateMomentum63()]
