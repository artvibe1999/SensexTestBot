"""The 20 SENSEX PRO single-leg option strategies.

Each class encodes the numbered specification in docs/ (entry, exit, stop,
target, trail, time window, premium/delta preferences, re-entry policy).
"""
from __future__ import annotations

from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from ..market import (SIDEWAYS, MarketContext, is_bear_engulfing, is_bear_pin, is_bull_engulfing,
                      is_bull_pin, is_doji, is_inside)
from .base import BREAKOUT, CE, PE, REVERSAL, TREND, Signal, Strategy, sign


def _nearest_level(levels: list[float], price: float, direction: str) -> Optional[float]:
    """Nearest level strictly beyond `price` in the trade direction."""
    if direction == CE:
        above = [lv for lv in levels if lv > price]
        return min(above) if above else None
    below = [lv for lv in levels if lv < price]
    return max(below) if below else None


# 1 ---------------------------------------------------------------------------
class OpeningRangeBreakout(Strategy):
    sid, name, category = "SENSEX_MOM_01", "Opening Range Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(9, 50), time(10, 30), time(15, 15), 45
    prem_min, prem_max = 200, 400
    trail_kind = "price"

    def entry(self, ctx: MarketContext) -> Optional[Signal]:
        orb = ctx.orb(30)
        if orb is None or (not np.isnan(ctx.daily_adx) and ctx.daily_adx < 20):
            return None
        hi, lo = orb
        c, p = ctx.c(0), ctx.c(1)
        if c["rvol"] <= 1.5 or c["body_pct"] <= 0.6:
            return None
        if c["bull"] and c["close"] > hi and p["close"] <= hi:
            d, sl = CE, float(c["low"])
        elif c["bear"] and c["close"] < lo and p["close"] >= lo:
            d, sl = PE, float(c["high"])
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(c["close"], sl, 2.0, d), book_fraction=0.5,
                      prem_sl_pct=0.15, note=f"ORB {lo:.0f}-{hi:.0f} break, RVOL {c['rvol']:.1f}")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["ema9"]) < 0:
            return "closed across 9 EMA"
        if ctx.close_time >= time(10, 30):
            r = abs(pos["underlying_entry"] - (pos.get("sl_price") or pos["underlying_entry"])) or 1
            if sign(pos["direction"]) * (c["close"] - pos["underlying_entry"]) < 0.5 * r:
                return "no momentum by 10:30"
        return None

    def trail_level(self, ctx, pos):
        c = ctx.last
        return float(c["low"] if pos["direction"] == CE else c["high"])


# 2 ---------------------------------------------------------------------------
class LiquiditySweepReversal(Strategy):
    sid, name, category = "SENSEX_TRAP_02", "Liquidity Sweep Reversal", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    delta_target, delta_min, delta_max = 0.40, 0.33, 0.47
    prem_min, prem_max = 150, 300
    reentry = "setup"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if c["adx"] > 30 or ctx.n_today < 4:
            return None
        lv = ctx.levels()
        for name, d in (("R1", PE), ("PDH", PE), ("S1", CE), ("PDL", CE)):
            level = lv[name]
            for back in (1, 2):
                b = ctx.c(back)
                before = ctx.c(back + 1)
                broke = (b["high"] > level) if d == PE else (b["low"] < level)
                fresh = (before["close"] < level) if d == PE else (before["close"] > level)
                if not (broke and fresh):
                    continue
                back_inside = (c["close"] < level) if d == PE else (c["close"] > level)
                pattern = (is_bear_engulfing(c, p) or is_bear_pin(c)) if d == PE else \
                          (is_bull_engulfing(c, p) or is_bull_pin(c))
                absorption = c["volume"] >= b["volume"] > 0 and b["volume"] >= b["vol_avg20"]
                if back_inside and pattern and absorption:
                    wick = ctx.df.iloc[-1 - back:]
                    sl = float(wick["high"].max()) if d == PE else float(wick["low"].min())
                    tgt = _nearest_level([float(c["vwap"]), lv["P"]], float(c["close"]), d)
                    if tgt is None:
                        tgt = self.rr_target(c["close"], sl, 1.5, d)
                    return Signal(d, sl_price=sl, target=tgt, setup_key=name,
                                  note=f"trap at {name} {level:.0f}")
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 3 ---------------------------------------------------------------------------
class VwapPullback(Strategy):
    sid, name, category = "SENSEX_VWAP_03", "Mid-Session VWAP Pullback", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 180
    prem_min, prem_max = 250, 450
    expiry_rule = "weekly_2pm"
    reentry = "yes"

    def entry(self, ctx):
        c, p, p2 = ctx.c(0), ctx.c(1), ctx.c(2)
        slope = ctx.vwap_slope_bps(3)
        if c["adx"] <= 25 or abs(slope) < 2:
            return None
        pullback_dry = (p["volume"] + p2["volume"]) / 2 < c["vol_avg20"] and c["volume"] > p["volume"]
        if not pullback_dry:
            return None
        vw = float(c["vwap"])
        if c["plus_di"] > c["minus_di"] and slope > 0 and c["low"] <= vw * 1.001 and c["close"] > vw \
                and (is_bull_pin(c) or is_bull_engulfing(c, p)):
            d = CE
        elif c["minus_di"] > c["plus_di"] and slope < 0 and c["high"] >= vw * 0.999 and c["close"] < vw \
                and (is_bear_pin(c) or is_bear_engulfing(c, p)):
            d = PE
        else:
            return None
        swing = ctx.swing_high(12) if d == CE else ctx.swing_low(12)
        tgt = swing if sign(d) * (swing - c["close"]) > 0 else self.rr_target(c["close"], vw, 1.5, d)
        return Signal(d, sl_close=vw, target=tgt, note=f"VWAP {vw:.0f} rejection")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0:
            return "closed across VWAP"
        return None

    def trail_level(self, ctx, pos):
        c = ctx.last
        want = 1 if pos["direction"] == CE else -1
        return float(c["st"]) if c["st_dir"] == want else None


# 4 ---------------------------------------------------------------------------
class EmaAdxTrend(Strategy):
    sid, name, category = "SENSEX_TREND_04", "EMA & ADX Trend Continuation", TREND
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    reentry = "yes"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if c["adx"] <= 30:
            return None
        if not (p["volume"] < p["vol_avg20"] and c["volume"] > c["vol_avg20"]):
            return None
        if c["ema9"] > c["ema21"] and p["low"] <= p["ema9"] and p["close"] >= p["ema21"] \
                and is_bull_engulfing(c, p):
            d = CE
        elif c["ema9"] < c["ema21"] and p["high"] >= p["ema9"] and p["close"] <= p["ema21"] \
                and is_bear_engulfing(c, p):
            d = PE
        else:
            return None
        e21 = float(c["ema21"])
        return Signal(d, sl_close=e21, target=self.rr_target(c["close"], e21, 2.0, d),
                      note=f"9EMA pullback, ADX {c['adx']:.0f}")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["ema21"]) < 0:
            return "closed across 21 EMA"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema21"])


# 5 ---------------------------------------------------------------------------
class RsiDivergencePivot(Strategy):
    sid, name, category = "SENSEX_REV_05", "RSI Divergence at Pivot", REVERSAL
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 90
    prem_min, prem_max = 150, 350
    reentry = "setup"
    trail_kind = "price"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if c["volume"] <= 1.5 * p["volume"] or len(ctx.df) < 20:
            return None
        lv = ctx.levels()
        window = ctx.df.iloc[-16:-2]
        for name, d, nxt in (("R1", PE, "P"), ("R2", PE, "R1"), ("S1", CE, "P"), ("S2", CE, "S1")):
            level = lv[name]
            if d == PE:
                near = abs(c["high"] - level) / level <= 0.001 or (c["high"] > level > c["close"])
                if not near:
                    continue
                ph = window["high"].idxmax()
                div = c["high"] > window.loc[ph, "high"] and c["rsi"] < window.loc[ph, "rsi"]
                pattern = is_bear_pin(c) or is_bear_engulfing(c, p)
                if div and pattern:
                    return Signal(PE, sl_price=level + 10, target=lv[nxt], setup_key=name,
                                  note=f"bearish RSI divergence at {name} {level:.0f}")
            else:
                near = abs(c["low"] - level) / level <= 0.001 or (c["low"] < level < c["close"])
                if not near:
                    continue
                pl = window["low"].idxmin()
                div = c["low"] < window.loc[pl, "low"] and c["rsi"] > window.loc[pl, "rsi"]
                pattern = is_bull_pin(c) or is_bull_engulfing(c, p)
                if div and pattern:
                    return Signal(CE, sl_price=level - 10, target=lv[nxt], setup_key=name,
                                  note=f"bullish RSI divergence at {name} {level:.0f}")
        return None

    def exit_on_close(self, ctx, pos):
        r_now, r_prev = ctx.c(0)["rsi"], ctx.c(1)["rsi"]
        if pos["direction"] == PE and r_prev >= 50 > r_now:
            return "RSI crossed below 50"
        if pos["direction"] == CE and r_prev <= 50 < r_now:
            return "RSI crossed above 50"
        return None

    def trail_level(self, ctx, pos):
        part = ctx.df.tail(3)
        return float(part["low"].min() if pos["direction"] == CE else part["high"].max())


# 6 ---------------------------------------------------------------------------
class VolatilitySqueezeBreakout(Strategy):
    sid, name, category = "SENSEX_BRK_06", "Volatility Squeeze Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(11, 30), time(14, 45), time(15, 15), 120
    delta_target, delta_min, delta_max = 0.40, 0.33, 0.47
    prem_min, prem_max = 100, 250
    reentry = "setup"
    trail_kind = "price"

    def entry(self, ctx):
        c = ctx.c(0)
        prior = ctx.df.iloc[-7:-1]
        sq = prior[(prior["bb_upper"] < prior["kc_upper"]) & (prior["bb_lower"] > prior["kc_lower"])]
        if sq.empty or c["rvol"] <= 2.0 or c["body_pct"] <= 0.7:
            return None
        if c["bull"] and c["close"] > c["bb_upper"]:
            d = CE
        elif c["bear"] and c["close"] < c["bb_lower"]:
            d = PE
        else:
            return None
        mid = float(c["sma20"])
        return Signal(d, sl_close=mid, target=self.rr_target(c["close"], mid, 3.0, d),
                      setup_key=str(sq.index[0]), note="BB inside KC squeeze breakout")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["sma20"]) < 0:
            return "closed back inside BB mid (20 SMA)"
        return None

    def trail_level(self, ctx, pos):
        c = ctx.last
        ps = float(c["psar"])
        if np.isnan(ps):
            return None
        return ps if sign(pos["direction"]) * (c["close"] - ps) > 0 else None


# 7 ---------------------------------------------------------------------------
class GapFillFade(Strategy):
    """Spec's CALL/PUT line is inverted relative to its own hypothesis ("fill the gap",
    exit at PDC). Implemented per the hypothesis: gap-up fade = PUT, gap-down fade = CALL."""
    sid, name, category = "SENSEX_GAP_07", "Gap Fill Fade", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 25), time(11, 0), time(11, 30), 120
    prem_min, prem_max = 250, 400

    def entry(self, ctx):
        if ctx.n_today < 2:
            return None
        first = ctx.today.iloc[0]
        gap = (first["open"] - ctx.pdc) / ctx.pdc
        if abs(gap) <= 0.005:
            return None
        c = ctx.c(0)
        runaway = first["rvol"] > 3 and first["body_pct"] > 0.7 and np.sign(first["close"] - first["open"]) == np.sign(gap)
        if runaway or c["volume"] <= first["volume"]:
            return None
        if gap > 0 and c["close"] > ctx.pdc and c["upper_wick"] > 0.5 * c["body"] and c["upper_wick"] > 0 \
                and c["close"] < c["vwap"]:
            return Signal(PE, sl_price=float(first["high"]), target=ctx.pdc, book_fraction=0.8,
                          note=f"gap up {gap:.2%} fade")
        if gap < 0 and c["close"] < ctx.pdc and c["lower_wick"] > 0.5 * c["body"] and c["lower_wick"] > 0 \
                and c["close"] > c["vwap"]:
            return Signal(CE, sl_price=float(first["low"]), target=ctx.pdc, book_fraction=0.8,
                          note=f"gap down {gap:.2%} fade")
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 8 ---------------------------------------------------------------------------
class VolumeClimax(Strategy):
    sid, name, category = "SENSEX_VOL_08", "Volume Spread Analysis Climax", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 30), time(15, 0), 60
    prem_min, prem_max = 200, 350

    @staticmethod
    def _near_resistance(ctx, price: float) -> bool:
        lv = list(ctx.levels().values()) + [round(price / 500) * 500]
        return any(abs(price - x) / x <= 0.0015 for x in lv)

    def entry(self, ctx):
        c, k = ctx.c(0), ctx.c(1)
        if ctx.n_today < 4:
            return None
        session_max = float(ctx.today["volume"].iloc[:-1].max())
        climax = k["rvol"] >= 3 and k["volume"] >= session_max and k["range"] >= 1.5 * k["atr"]
        if not climax:
            return None
        if k["bull"] and k["close"] > k["ema21"] + k["atr"] and self._near_resistance(ctx, k["high"]) \
                and (is_inside(c, k) or c["bear"]) and c["high"] <= k["high"]:
            return Signal(PE, sl_price=float(k["high"]), target=float(c["ema21"]), note="buying climax")
        if k["bear"] and k["close"] < k["ema21"] - k["atr"] and self._near_resistance(ctx, k["low"]) \
                and (is_inside(c, k) or c["bull"]) and c["low"] >= k["low"]:
            return Signal(CE, sl_price=float(k["low"]), target=float(c["ema21"]), note="selling climax")
        return None

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["ema21"]) >= 0:
            return "reached 21 EMA"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 9 ---------------------------------------------------------------------------
class InsideBarBreakout(Strategy):
    sid, name, category = "SENSEX_IB_09", "Inside Bar Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 45
    delta_target, delta_min, delta_max = 0.45, 0.38, 0.52
    prem_min, prem_max = 150, 300
    reentry = "setup"

    def entry(self, ctx):
        c, ib, mother = ctx.c(0), ctx.c(1), ctx.c(2)
        if c["adx"] < 20 or not is_inside(ib, mother) or c["volume"] <= mother["volume"]:
            return None
        slope = c["ema9"] - ctx.c(3)["ema9"]
        if c["close"] > mother["high"] and slope > 0:
            d, sl = CE, float(ib["low"])
        elif c["close"] < mother["low"] and slope < 0:
            d, sl = PE, float(ib["high"])
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(c["close"], sl, 1.5, d),
                      setup_key=str(ctx.df.index[-2]),
                      meta={"mother_high": float(mother["high"]), "mother_low": float(mother["low"])},
                      note="inside bar breakout")

    def exit_on_close(self, ctx, pos):
        c, m = ctx.last, pos.get("meta", {})
        if m and m["mother_low"] < c["close"] < m["mother_high"]:
            return "closed back inside mother bar"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 10 --------------------------------------------------------------------------
class SupertrendPullback(Strategy):
    sid, name, category = "SENSEX_SUP_10", "Supertrend Pullback", TREND
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 400
    reentry = "yes"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        flips = int((ctx.df["st_dir"].tail(12).diff().abs() > 0).sum())
        if flips > 1 or c["volume"] <= p["volume"]:
            return None
        st = float(c["st"])
        if c["st_dir"] == 1 and c["low"] <= st * 1.002 and c["close"] > st and is_bull_pin(c, 0.4):
            d = CE
        elif c["st_dir"] == -1 and c["high"] >= st * 0.998 and c["close"] < st and is_bear_pin(c, 0.4):
            d = PE
        else:
            return None
        swing = ctx.swing_high(12) if d == CE else ctx.swing_low(12)
        tgt = swing if sign(d) * (swing - c["close"]) > 0 else self.rr_target(c["close"], st, 2.0, d)
        return Signal(d, sl_close=st, target=tgt, note=f"Supertrend {st:.0f} bounce")

    def exit_on_close(self, ctx, pos):
        want = 1 if pos["direction"] == CE else -1
        if ctx.last["st_dir"] != want:
            return "Supertrend flipped"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["st"])


# 11 --------------------------------------------------------------------------
class FalseBreakdownSpring(Strategy):
    sid, name, category = "SENSEX_FALSE_11", "False Breakdown / Spring", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350

    def entry(self, ctx):
        c, p, p2 = ctx.c(0), ctx.c(1), ctx.c(2)
        if ctx.n_today < 3 or c["volume"] <= p["volume"]:
            return None
        lv = ctx.levels()
        if not (c["adx"] > 35 and c["minus_di"] > c["plus_di"]):
            if p2["close"] >= ctx.pdl and p["close"] < ctx.pdl and c["close"] > ctx.pdl \
                    and is_bull_engulfing(c, p):
                sl = float(min(p["low"], c["low"]))
                tgt = _nearest_level([float(c["vwap"]), lv["P"]], float(c["close"]), CE) \
                    or self.rr_target(c["close"], sl, 1.5, CE)
                return Signal(CE, sl_price=sl, target=tgt, note=f"spring at PDL {ctx.pdl:.0f}")
        if not (c["adx"] > 35 and c["plus_di"] > c["minus_di"]):
            if p2["close"] <= ctx.pdh and p["close"] > ctx.pdh and c["close"] < ctx.pdh \
                    and is_bear_engulfing(c, p):
                sl = float(max(p["high"], c["high"]))
                tgt = _nearest_level([float(c["vwap"]), lv["P"]], float(c["close"]), PE) \
                    or self.rr_target(c["close"], sl, 1.5, PE)
                return Signal(PE, sl_price=sl, target=tgt, note=f"upthrust at PDH {ctx.pdh:.0f}")
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 12 --------------------------------------------------------------------------
class ExpiryGammaScalp(Strategy):
    sid, name, category = "SENSEX_0DTE_12", "Expiry Day Gamma Scalp", BREAKOUT
    start, end, time_exit, max_hold_min = time(13, 35), time(15, 0), time(15, 20), 30
    delta_target, delta_min, delta_max = 0.40, 0.30, 0.50
    prem_min, prem_max = 30, 100
    expiry_rule = "0dte"
    capital_pct = 0.05
    trail_kind = "price"
    uses_3min = True

    def entry(self, ctx):
        if not ctx.is_expiry_day:
            return None
        c, p = ctx.c(0), ctx.c(1)
        hi, lo = ctx.day_high_low(exclude_last=1)
        if c["rvol"] <= 1.5 or c["volume"] <= p["volume"] or c["body_pct"] < 0.6:
            return None
        if c["bull"] and c["close"] > hi:
            d = CE
        elif c["bear"] and c["close"] < lo:
            d = PE
        else:
            return None
        return Signal(d, prem_sl_pct=0.30, prem_target_pct=0.50, book_fraction=0.5,
                      note="0DTE day-range break")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        opposing = c["bear"] if pos["direction"] == CE else c["bull"]
        if opposing and ctx.df.index[-1] > pd.Timestamp(pos["entry_candle"]):
            return "momentum stalled (opposing candle)"
        return None

    def trail_level(self, ctx, pos):
        df3 = getattr(ctx, "df3", None)
        c = df3.iloc[-1] if df3 is not None and len(df3) else ctx.last
        return float(c["low"] if pos["direction"] == CE else c["high"])


# 13 --------------------------------------------------------------------------
class WmaCrossScalp(Strategy):
    sid, name, category = "SENSEX_WMA_13", "Weighted MA Crossover Scalp", TREND
    start, end, time_exit, max_hold_min = time(9, 35), time(15, 10), time(15, 15), 20
    delta_target, delta_min, delta_max = 0.60, 0.53, 0.67
    prem_min, prem_max = 300, 500
    reentry = "yes"
    WINDOWS = ((time(9, 30), time(10, 30)), (time(14, 0), time(15, 15)))

    def in_window(self, ctx):
        t = ctx.close_time
        return any(a <= t <= b for a, b in self.WINDOWS) and t <= self.end

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if np.isnan(c["wma13"]) or np.isnan(p["wma13"]):
            return None
        lows = ctx.df.iloc[-6:-1]
        if p["wma5"] <= p["wma13"] and c["wma5"] > c["wma13"] and c["close"] > max(c["wma5"], c["wma13"]):
            d, sl = CE, float(lows["low"].min())
        elif p["wma5"] >= p["wma13"] and c["wma5"] < c["wma13"] and c["close"] < min(c["wma5"], c["wma13"]):
            d, sl = PE, float(lows["high"].max())
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(c["close"], sl, 1.5, d), note="5/13 WMA cross")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["wma5"] - c["wma13"]) < 0:
            return "WMA crossed back"
        t = ctx.close_time
        if not any(a <= t <= b for a, b in self.WINDOWS):
            return "momentum window ended"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["wma13"])


# 14 --------------------------------------------------------------------------
class StochasticRangeReversion(Strategy):
    sid, name, category = "SENSEX_RNG_14", "Stochastic Range Reversion", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 30), time(15, 0), 120
    prem_min, prem_max = 150, 300
    reentry = "yes"
    trail_kind = "none"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        mid_slope = abs(c["bb_mid"] - ctx.c(5)["bb_mid"]) / c["bb_mid"]
        sideways = ctx.regime == SIDEWAYS or (c["adx"] < 20 and mid_slope < 0.0005)
        if not sideways or p["volume"] >= p["vol_avg20"]:
            return None
        if min(p["low"], c["low"]) <= c["bb_lower"] and p["stoch_k"] < 20 <= c["stoch_k"] \
                and c["bull"] and c["lower_wick_pct"] >= 0.3:
            return Signal(CE, sl_close=float(c["bb_lower"]), target=float(c["bb_mid"]), note="stoch up from <20 at lower BB")
        if max(p["high"], c["high"]) >= c["bb_upper"] and p["stoch_k"] > 80 >= c["stoch_k"] \
                and c["bear"] and c["upper_wick_pct"] >= 0.3:
            return Signal(PE, sl_close=float(c["bb_upper"]), target=float(c["bb_mid"]), note="stoch down from >80 at upper BB")
        return None

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if pos["direction"] == CE:
            if c["close"] < c["bb_lower"]:
                return "closed below lower BB"
            if c["stoch_k"] >= 80:
                return "stochastic reached 80"
            if c["close"] >= c["bb_mid"]:
                return "reached middle BB"
        else:
            if c["close"] > c["bb_upper"]:
                return "closed above upper BB"
            if c["stoch_k"] <= 20:
                return "stochastic reached 20"
            if c["close"] <= c["bb_mid"]:
                return "reached middle BB"
        return None


# 15 --------------------------------------------------------------------------
class DojiContinuation(Strategy):
    sid, name, category = "SENSEX_DOJI_15", "Doji Continuation", TREND
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 60

    def entry(self, ctx):
        c, dj = ctx.c(0), ctx.c(1)
        if c["adx"] <= 25 or not is_doji(dj) or dj["volume"] >= dj["vol_avg20"] or c["volume"] <= c["vol_avg20"]:
            return None
        near = dj["low"] <= dj["ema9"] * 1.0005 and dj["high"] >= dj["ema9"] * 0.9995
        if not near:
            return None
        if c["ema9"] > c["ema21"] and c["close"] > dj["high"]:
            d, sl = CE, float(dj["low"])
        elif c["ema9"] < c["ema21"] and c["close"] < dj["low"]:
            d, sl = PE, float(dj["high"])
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(c["close"], sl, 2.0, d), note="doji at 9 EMA")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["ema9"]) < 0:
            return "closed across 9 EMA"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 16 --------------------------------------------------------------------------
class VwapCrossover(Strategy):
    sid, name, category = "SENSEX_VWAP_X_16", "VWAP Crossover", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 180
    prem_min, prem_max = 250, 400

    def entry(self, ctx):
        c = ctx.c(0)
        if ctx.vwap_crosses(12) >= 4 or c["rvol"] <= 1.5 or c["body_pct"] < 0.5:
            return None
        vw = float(c["vwap"])
        if c["open"] < vw * 0.9998 and c["close"] > vw * 1.0002:
            d, sl = CE, float(c["low"])
        elif c["open"] > vw * 1.0002 and c["close"] < vw * 0.9998:
            d, sl = PE, float(c["high"])
        else:
            return None
        lv = ctx.levels()
        hi, lo = ctx.day_high_low()
        tgt = _nearest_level([lv["P"], lv["R1"], lv["R2"], lv["S1"], lv["S2"], lv["PDH"], lv["PDL"], hi, lo],
                             float(c["close"]), d)
        risk = abs(c["close"] - sl)
        if tgt is None or abs(tgt - c["close"]) < risk:
            tgt = self.rr_target(c["close"], sl, 2.0, d)
        return Signal(d, sl_price=sl, target=tgt, note=f"full-body VWAP cross {vw:.0f}")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0:
            return "crossed back across VWAP"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema21"])


# 17 --------------------------------------------------------------------------
class MacdZeroReject(Strategy):
    sid, name, category = "SENSEX_MACD_17", "MACD Zero-Line Reject", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    reentry = "yes"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        m = ctx.df["macd"].iloc[-6:-1]
        a = float(c["atr"])
        h_now, h_prev = c["macd_hist"], p["macd_hist"]
        if c["macd"] > 0 and 0 <= m.min() <= 0.25 * a and c["macd"] > p["macd"] and h_now > h_prev and h_now > 0 \
                and is_bull_engulfing(c, p):
            d, sl = CE, ctx.swing_low(6, skip=0)
        elif c["macd"] < 0 and -0.25 * a <= m.max() <= 0 and c["macd"] < p["macd"] and h_now < h_prev and h_now < 0 \
                and is_bear_engulfing(c, p):
            d, sl = PE, ctx.swing_high(6, skip=0)
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(c["close"], sl, 2.0, d), note="MACD zero-line bounce")

    def exit_on_close(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["macd"] - c["macd_signal"]) < 0:
            return "MACD signal-line crossover"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 18 --------------------------------------------------------------------------
class MorningConsolidationBreakout(Strategy):
    sid, name, category = "SENSEX_MCD_18", "Morning Consolidation Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(10, 35), time(14, 45), time(15, 15), 400
    prem_min, prem_max = 200, 350

    def entry(self, ctx):
        rng = ctx.range_until(time(10, 30))
        if rng is None:
            return None
        hi, lo = rng
        mid = (hi + lo) / 2
        if (hi - lo) / mid >= 0.003:
            return None
        c, p = ctx.c(0), ctx.c(1)
        if c["rvol"] <= 2.0:
            return None
        if c["close"] > hi and p["close"] <= hi:
            d = CE
        elif c["close"] < lo and p["close"] >= lo:
            d = PE
        else:
            return None
        return Signal(d, sl_price=mid, target=self.rr_target(c["close"], mid, 3.0, d),
                      meta={"range_high": hi, "range_low": lo}, note=f"morning range {lo:.0f}-{hi:.0f} break")

    def exit_on_close(self, ctx, pos):
        c, m = ctx.last, pos.get("meta", {})
        if not m:
            return None
        if pos["direction"] == CE and c["close"] < m["range_high"] and c["close"] < c["vwap"]:
            return "back inside range below VWAP"
        if pos["direction"] == PE and c["close"] > m["range_low"] and c["close"] > c["vwap"]:
            return "back inside range above VWAP"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema9"])


# 19 --------------------------------------------------------------------------
class FibRetracement(Strategy):
    sid, name, category = "SENSEX_FIB_19", "Fibonacci 0.618 Retracement", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 180
    delta_target, delta_min, delta_max = 0.55, 0.48, 0.62
    prem_min, prem_max = 250, 450

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 10:
            return None
        c = t.iloc[-1]
        hist = t.iloc[:-3]
        price = float(c["close"])
        for d in (CE, PE):
            if d == CE:
                ext_i = int(np.argmax(hist["high"].to_numpy()))
                ext = float(hist["high"].iloc[ext_i])
                origin = float(hist["low"].iloc[: ext_i + 1].min()) if ext_i > 0 else None
            else:
                ext_i = int(np.argmin(hist["low"].to_numpy()))
                ext = float(hist["low"].iloc[ext_i])
                origin = float(hist["high"].iloc[: ext_i + 1].max()) if ext_i > 0 else None
            if origin is None or abs(ext - origin) < 0.004 * price:
                continue
            impulse = t.iloc[: ext_i + 1]
            pull = t.iloc[ext_i + 1: -1]
            if len(pull) < 2:
                continue
            size = abs(ext - origin)
            f618 = ext - sign(d) * 0.618 * size
            f786 = ext - sign(d) * 0.786 * size
            low_vol_pullback = pull["volume"].mean() < impulse["volume"].mean()
            if d == CE:
                intact = pull["low"].min() > f786 and pull["high"].max() < ext
                touch = c["low"] <= f618 * 1.0005 and c["close"] > f618 and is_bull_pin(c, 0.4)
            else:
                intact = pull["high"].max() < f786 and pull["low"].min() > ext
                touch = c["high"] >= f618 * 0.9995 and c["close"] < f618 and is_bear_pin(c, 0.4)
            if intact and touch and low_vol_pullback and c["volume"] > pull["volume"].mean():
                return Signal(d, sl_close=f786, target=ext, meta={"f786": f786},
                              note=f"0.618 retrace {f618:.0f} of {origin:.0f}->{ext:.0f}")
        return None

    def exit_on_close(self, ctx, pos):
        f786 = pos.get("meta", {}).get("f786")
        if f786 and sign(pos["direction"]) * (ctx.last["close"] - f786) < 0:
            return "broke 0.786 level"
        return None

    def trail_level(self, ctx, pos):
        return float(ctx.last["ema21"])


# 20 --------------------------------------------------------------------------
class EndOfDaySqueeze(Strategy):
    sid, name, category = "SENSEX_EOD_20", "End of Day Squeeze", BREAKOUT
    start, end, time_exit, max_hold_min = time(14, 35), time(15, 10), time(15, 20), 45
    trail_kind = "price"

    def entry(self, ctx):
        t = ctx.today
        flag = t[(t.index.time >= time(13, 30))].iloc[:-1]
        if len(flag) < 4:
            return None
        c = t.iloc[-1]
        fh, fl = float(flag["high"].max()), float(flag["low"].min())
        price = float(c["close"])
        if (fh - fl) / price > 0.0025 or c["volume"] <= c["vol_avg20"]:
            return None
        day_hi, day_lo = ctx.day_high_low(exclude_last=1)
        day_open = float(t.iloc[0]["open"])
        if c["bull"] and price > fh and day_hi - fh <= 0.0015 * price and price > c["vwap"] and price > day_open:
            d, sl = CE, fl
        elif c["bear"] and price < fl and fl - day_lo <= 0.0015 * price and price < c["vwap"] and price < day_open:
            d, sl = PE, fh
        else:
            return None
        return Signal(d, sl_price=sl, target=self.rr_target(price, sl, 1.5, d), note=f"EOD flag {fl:.0f}-{fh:.0f} break")

    def trail_level(self, ctx, pos):
        c = ctx.last
        return float(c["low"] if pos["direction"] == CE else c["high"])


ALL_STRATEGIES: list[Strategy] = [
    OpeningRangeBreakout(), LiquiditySweepReversal(), VwapPullback(), EmaAdxTrend(), RsiDivergencePivot(),
    VolatilitySqueezeBreakout(), GapFillFade(), VolumeClimax(), InsideBarBreakout(), SupertrendPullback(),
    FalseBreakdownSpring(), ExpiryGammaScalp(), WmaCrossScalp(), StochasticRangeReversion(), DojiContinuation(),
    VwapCrossover(), MacdZeroReject(), MorningConsolidationBreakout(), FibRetracement(), EndOfDaySqueeze(),
]
from .catalog_21_60 import STRATEGIES_21_60  # noqa: E402  (strategies 21-60, lower priority than 1-20)

ALL_STRATEGIES += STRATEGIES_21_60
STRATEGY_MAP = {s.sid: s for s in ALL_STRATEGIES}
