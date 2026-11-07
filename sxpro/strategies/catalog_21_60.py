"""SENSEX PRO strategies 21-60 (docs/sensex_pro_additional_strategies_21_40.md and _41_60.md).

Same contract as catalog.py: each strategy reads closed 5-minute SENSEX candles from the
MarketContext and returns a Signal; the engine does strike selection, sizing, risk and
execution. Point thresholds (e.g. "range < 30 points") are taken literally from the spec.

Mapping notes (where a rule cannot be expressed exactly on closed 5-minute candles):
* "Enter on the open of the next candle" / "on the break of X" = enter at the close of the
  candle that confirms it (the engine enters at candle close).
* Volume = SENSEX futures volume live (constituent traded-value proxy in the backtest).
* Close-based stops ("close below VWAP / 21 EMA") are checked on each candle close; price
  stops are checked on every tick by the engine.
* 37 needs breadth, 39/48 need option OI, 60 needs NIFTY 50: fetched live on demand. The
  backtest has breadth and NIFTY history but no historical option OI, so 39 and 48 cannot
  trade in the backtest.
"""
from __future__ import annotations

from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from ..market import MarketContext, is_bear_engulfing, is_bear_pin, is_bull_engulfing, is_bull_pin, is_doji, is_inside
from .base import BREAKOUT, CE, PE, REVERSAL, TREND, Signal, Strategy, sign

ALL_DAY = 330  # "rest of day" holding limit in minutes


# ============================================================ helpers
def rev_up(c: pd.Series, p: pd.Series, wick: float = 0.5) -> bool:
    return is_bull_pin(c, wick) or is_bull_engulfing(c, p)


def rev_dn(c: pd.Series, p: pd.Series, wick: float = 0.5) -> bool:
    return is_bear_pin(c, wick) or is_bear_engulfing(c, p)


def pivots(df: pd.DataFrame, col: str, left: int = 2, right: int = 2) -> list[int]:
    """Positional indexes of fractal pivots (high: strictly above `left`/`right` neighbours)."""
    a = df[col].to_numpy()
    out = []
    for i in range(left, len(a) - right):
        win = np.concatenate([a[i - left:i], a[i + 1:i + 1 + right]])
        if (col == "high" and a[i] > win.max()) or (col == "low" and a[i] < win.min()):
            out.append(i)
    return out


def bars_since_entry(ctx: MarketContext, pos: dict) -> pd.DataFrame:
    entry = pd.Timestamp(pos["entry_time"])
    if entry.tzinfo is None:
        entry = entry.tz_localize(ctx.df.index.tz)
    return ctx.today[ctx.today.index + pd.Timedelta(minutes=5) > entry]


def anchored_vwap(part: pd.DataFrame) -> float:
    tp = (part["high"] + part["low"] + part["close"]) / 3
    vol = part["volume"].astype(float)
    return float((tp * vol).sum() / vol.sum()) if vol.sum() > 0 else float(tp.mean())


class Spec(Strategy):
    """Base for strategies 21-60: close-based stops, declarative trails, signal builder."""

    trail: Optional[str] = None  # ema9 | ema13 | ema21 | vwap | prev | swing3 | None

    def make(self, d: str, entry: float, stop: float, rr: Optional[float] = None,
             target: Optional[float] = None, close_stop: bool = False, note: str = "",
             meta: Optional[dict] = None, key: str = "", prem_sl: Optional[float] = None,
             prem_target: Optional[float] = None, rr_fallback: Optional[float] = None) -> Optional[Signal]:
        if sign(d) * (entry - stop) <= 0:
            return None  # stop on the wrong side: no defined risk
        tgt = target
        if tgt is not None and sign(d) * (tgt - entry) <= 0:
            tgt = None if rr_fallback is None else self.rr_target(entry, stop, rr_fallback, d)
            if tgt is None:
                return None  # structural target already behind price
        elif tgt is None and rr:
            tgt = self.rr_target(entry, stop, rr, d)
        m = dict(meta or {})
        if close_stop:
            m["sl_close"] = stop
        return Signal(d, sl_price=None if close_stop else stop, sl_close=stop if close_stop else None,
                      target=tgt, prem_sl_pct=prem_sl, prem_target_pct=prem_target, setup_key=key,
                      note=note, meta=m)

    def exit_rule(self, ctx: MarketContext, pos: dict) -> Optional[str]:
        return None

    def exit_on_close(self, ctx, pos):
        slc = (pos.get("meta") or {}).get("sl_close")
        if slc is not None and sign(pos["direction"]) * (float(ctx.last["close"]) - slc) < 0:
            return f"closed beyond stop {slc:.0f}"
        return self.exit_rule(ctx, pos)

    def trail_level(self, ctx, pos):
        c, d = ctx.last, pos["direction"]
        if self.trail in ("ema9", "ema13", "ema21", "vwap"):
            return float(c[self.trail])
        if self.trail == "prev":
            return float(c["low"] if d == CE else c["high"])
        if self.trail == "swing3":
            part = ctx.df.tail(3)
            return float(part["low"].min() if d == CE else part["high"].max())
        return None

    @staticmethod
    def no_new_extreme(ctx: MarketContext, pos: dict, n: int = 3) -> Optional[str]:
        """'Fails to make a new high/low within n candles' of the entry candle."""
        bars = bars_since_entry(ctx, pos)
        if len(bars) < n:
            return None
        ref = ctx.today[ctx.today.index + pd.Timedelta(minutes=5) <= pd.Timestamp(pos["entry_time"])]
        if ref.empty:
            return None
        e = ref.iloc[-1]
        if pos["direction"] == CE and bars["high"].max() <= e["high"]:
            return f"no new high in {n} candles"
        if pos["direction"] == PE and bars["low"].min() >= e["low"]:
            return f"no new low in {n} candles"
        return None


# ============================================================ 21-40
class VwapDeviation21(Spec):
    sid, name, category = "SENSEX_VWAP_DEV_21", "VWAP Standard Deviation Reversion", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 0), 90
    prem_min, prem_max = 150, 350
    reentry, trail = "yes", "ema9"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if ctx.n_today < 4 or c["adx"] > 30:
            return None
        up, lo = c["vwap"] + 2 * c["vwap_sd"], c["vwap"] - 2 * c["vwap_sd"]
        price = float(c["close"])
        for d in (CE, PE):
            if d == CE:
                touch = c if c["low"] <= lo else (p if p["low"] <= p["vwap"] - 2 * p["vwap_sd"] else None)
                rev = (is_bull_pin(c, 0.5) and touch is c) or (touch is p and is_bull_engulfing(c, p))
                stop = float(min(c["low"], p["low"]) if touch is p else c["low"])
            else:
                touch = c if c["high"] >= up else (p if p["high"] >= p["vwap"] + 2 * p["vwap_sd"] else None)
                rev = (is_bear_pin(c, 0.5) and touch is c) or (touch is p and is_bear_engulfing(c, p))
                stop = float(max(c["high"], p["high"]) if touch is p else c["high"])
            if touch is None or not rev or touch["rvol"] < 1.5:
                continue
            if touch is p and c["volume"] >= p["volume"]:
                continue  # volume must drop on the reversal candle
            return self.make(d, price, stop, target=float(c["vwap"]), key=str(ctx.df.index[-1]),
                             note=f"2SD VWAP band reject ({lo:.0f}/{up:.0f})")
        return None


class OpenDrive22(Spec):
    sid, name, category = "SENSEX_OPEN_DRV_22", "Institutional Open Drive", BREAKOUT
    start, end, time_exit, max_hold_min = time(9, 20), time(9, 20), time(11, 30), 120
    delta_target, delta_min, delta_max = 0.60, 0.53, 0.67
    prem_min, prem_max = 300, 500
    trail = "ema9"

    def entry(self, ctx):
        if ctx.n_today != 1:
            return None
        c = ctx.c(0)
        if c["body_pct"] <= 0.85 or c["rvol"] <= 3.0:
            return None
        mid = float((c["high"] + c["low"]) / 2)
        if c["bull"] and c["close"] > ctx.pdh:
            return self.make(CE, float(c["close"]), mid, rr=2.5, note="bullish open-drive marubozu above PDH")
        if c["bear"] and c["close"] < ctx.pdl:
            return self.make(PE, float(c["close"]), mid, rr=2.5, note="bearish open-drive marubozu below PDL")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0:
            return "closed across VWAP"
        return None


class PdcBounce23(Spec):
    sid, name, category = "SENSEX_PDC_BNC_23", "Previous Day Close Bounce", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350
    reentry, max_entries, trail, trail_kind = "yes", 2, "swing3", "price"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if ctx.n_today < 3:
            return None
        pdc, price = ctx.pdc, float(c["close"])
        tol = 0.0003 * price
        prior = ctx.today.iloc[-4:-1]
        hi, lo = ctx.day_high_low()
        if c["low"] <= pdc + tol and price > pdc and p["close"] > pdc and (is_bull_pin(c) or is_bull_engulfing(c, p)) \
                and c["volume"] > prior["volume"].mean():
            return self.make(CE, price, pdc - 15, target=hi, note=f"PDC {pdc:.0f} bounce")
        if c["high"] >= pdc - tol and price < pdc and p["close"] < pdc and (is_bear_pin(c) or is_bear_engulfing(c, p)) \
                and c["volume"] > prior["volume"].mean():
            return self.make(PE, price, pdc + 15, target=lo, note=f"PDC {pdc:.0f} rejection")
        return None

    def exit_rule(self, ctx, pos):
        return self.no_new_extreme(ctx, pos, 3)


class OrbFail24(Spec):
    sid, name, category = "SENSEX_ORB_FAIL_24", "ORB Fade / Trap", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 35), time(13, 45), time(14, 0), 120
    delta_target, delta_min, delta_max = 0.40, 0.33, 0.47
    prem_min, prem_max = 150, 300
    trail = "vwap"

    def entry(self, ctx):
        orb = ctx.orb(15)
        if orb is None or ctx.n_today < 5:
            return None
        hi, lo = orb
        c = ctx.c(0)
        price = float(c["close"])
        if c["body_pct"] < 0.5:
            return None
        for k in (1, 2):
            b = ctx.c(k)
            if ctx.n_today - 1 - k < 3:
                break
            if b["close"] > hi and price < hi and c["bear"] and b["rvol"] < 1.2 and c["volume"] > b["volume"]:
                stop = float(ctx.df["high"].iloc[-1 - k:].max())
                return self.make(PE, price, stop, target=lo, note=f"failed ORB high {hi:.0f}")
            if b["close"] < lo and price > lo and c["bull"] and b["rvol"] < 1.2 and c["volume"] > b["volume"]:
                stop = float(ctx.df["low"].iloc[-1 - k:].min())
                return self.make(CE, price, stop, target=hi, note=f"failed ORB low {lo:.0f}")
        return None


class AtrExpansion25(Spec):
    sid, name, category = "SENSEX_ATR_EXP_25", "ATR Expansion Continuation", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 400
    reentry, trail = "yes", "ema9"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if not (c["atr"] > c["atr_sma10"] and p["atr"] <= p["atr_sma10"]):
            return None
        if c["body_pct"] < 0.6 or c["rvol"] < 1.2:
            return None
        price = float(c["close"])
        if c["bull"] and price > c["ema21"]:
            return self.make(CE, price, float(c["ema21"]), rr=2.0, close_stop=True, note="ATR expansion up")
        if c["bear"] and price < c["ema21"]:
            return self.make(PE, price, float(c["ema21"]), rr=2.0, close_stop=True, note="ATR expansion down")
        return None

    def exit_rule(self, ctx, pos):
        return "ATR back below its SMA" if ctx.last["atr"] < ctx.last["atr_sma10"] else None


class LunchFade26(Spec):
    sid, name, category = "SENSEX_SESSION_T_26", "Lunch Hour Fade", TREND
    start, end, time_exit, max_hold_min = time(13, 35), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350
    trail = "vwap"

    def entry(self, ctx):
        t = ctx.today
        morning = t[t.index.time < time(12, 0)]
        lunch = t[(t.index.time >= time(12, 0)) & (t.index.time < time(13, 30))]
        if len(morning) < 20 or len(lunch) < 15:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        move = float(morning["close"].iloc[-1] - morning["open"].iloc[0])
        lh, ll = float(lunch["high"].max()), float(lunch["low"].min())
        drift = float(lunch["close"].iloc[-1] - lunch["open"].iloc[0])
        if abs(move) < 0.0035 * price or c["volume"] <= lunch["volume"].mean():
            return None
        if move > 0 and drift < 0 and price > lh and p["close"] <= lh:
            return self.make(CE, price, ll, rr=2.0, note=f"lunch range {ll:.0f}-{lh:.0f} break up")
        if move < 0 and drift > 0 and price < ll and p["close"] >= ll:
            return self.make(PE, price, lh, rr=2.0, note=f"lunch range {ll:.0f}-{lh:.0f} break down")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        if sign(pos["direction"]) * (c["macd"] - c["macd_signal"]) < 0:
            return "MACD crossed against trade"
        return None


class LiquidityGrab27(Spec):
    sid, name, category = "SENSEX_LIQ_GRAB_27", "Swing Liquidity Sweep", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    trail, trail_kind = "prev", "price"
    needs = ("vix",)

    def entry(self, ctx):
        vix = ctx.aux.get("vix")
        if vix is not None and len(vix) and float(vix.iloc[-1]) > 22:
            return None  # extremely high VIX
        df = ctx.df.tail(40)
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["range"] <= 0:
            return None
        for d, col in ((CE, "low"), (PE, "high")):
            piv = [i for i in pivots(df.iloc[:-3], col) if i < len(df) - 3]
            if not piv:
                continue
            i = piv[-1]
            lvl = float(df[col].iloc[i])
            after = df.iloc[i + 1:-2]
            sweep = df.iloc[-2:]
            if d == CE:
                if after["low"].min() <= lvl or sweep["low"].min() >= lvl or (sweep["close"] < lvl).sum() > 1:
                    continue
                if not (price > lvl + 0.2 * c["range"] and (is_bull_pin(c) or is_bull_engulfing(c, p))):
                    continue
                stop = float(sweep["low"].min())
                ph = [j for j in pivots(df.iloc[:-2], "high") if j > i]
                tgt = float(df["high"].iloc[ph[-1]]) if ph else None
            else:
                if after["high"].max() >= lvl or sweep["high"].max() <= lvl or (sweep["close"] > lvl).sum() > 1:
                    continue
                if not (price < lvl - 0.2 * c["range"] and (is_bear_pin(c) or is_bear_engulfing(c, p))):
                    continue
                stop = float(sweep["high"].max())
                pl = [j for j in pivots(df.iloc[:-2], "low") if j > i]
                tgt = float(df["low"].iloc[pl[-1]]) if pl else None
            if float(sweep["rvol"].max()) < 1.5:
                continue
            return self.make(d, price, stop, target=tgt, rr_fallback=2.0, rr=2.0,
                             note=f"swept swing {col} {lvl:.0f}")
        return None


class VwapPin28(Spec):
    sid, name, category = "SENSEX_VWAP_PIN_28", "Expiry Day VWAP Pinning", REVERSAL
    start, end, time_exit, max_hold_min = time(14, 0), time(14, 45), time(15, 20), 80
    delta_target, delta_min, delta_max = 0.70, 0.62, 0.78
    prem_min, prem_max = 100, 200
    expiry_rule, trail = "0dte", "ema9"

    def entry(self, ctx):
        if not ctx.is_expiry_day:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price, vw = float(c["close"]), float(c["vwap"])
        if abs(price - vw) / vw <= 0.005 or c["adx"] >= ctx.c(3)["adx"]:
            return None
        if c["volume"] >= ctx.df["volume"].iloc[-4:-1].mean():
            return None
        hi, lo = ctx.day_high_low()
        if price < vw and c["bull"] and p["bear"]:
            return self.make(CE, price, lo, target=vw, note=f"0DTE pin to VWAP {vw:.0f}")
        if price > vw and c["bear"] and p["bull"]:
            return self.make(PE, price, hi, target=vw, note=f"0DTE pin to VWAP {vw:.0f}")
        return None


class VixCrush29(Spec):
    sid, name, category = "SENSEX_VIX_CRUSH_29", "VIX Contraction Short-Covering", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), ALL_DAY
    prem_min, prem_max = 200, 350
    trail = "ema21"
    needs = ("vix",)

    def entry(self, ctx):
        vix = ctx.aux.get("vix")
        if vix is None or len(vix) < 6:
            return None
        drop = (float(vix.iloc[0]) - float(vix.iloc[-1])) / float(vix.iloc[0])
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        day_open = float(ctx.today["open"].iloc[0])
        bearish_morning = float(ctx.today["low"].min()) < day_open * 0.997
        if drop <= 0.03 or not bearish_morning:
            return None
        if p["close"] <= p["vwap"] and price > c["vwap"] and c["bull"] and c["body_pct"] >= 0.6 \
                and c["volume"] > p["volume"]:
            _, lo = ctx.day_high_low()
            return self.make(CE, price, lo, rr=2.5, note=f"VIX -{drop:.1%}, VWAP reclaim")
        return None

    def exit_rule(self, ctx, pos):
        return "closed below 21 EMA" if ctx.last["close"] < ctx.last["ema21"] else None


class TrendExhaustion30(Spec):
    sid, name, category = "SENSEX_TREND_EXH_30", "Parabolic Exhaustion Fade", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 45
    delta_target, delta_min, delta_max = 0.40, 0.33, 0.47
    prem_min, prem_max = 150, 300
    capital_pct, trail_kind = 0.05, "none"

    def entry(self, ctx):
        c = ctx.c(0)
        run = [ctx.c(k) for k in (1, 2, 3, 4)]
        if not (is_doji(c, 0.15) or is_bear_pin(c, 0.5) or is_bull_pin(c, 0.5)):
            return None
        if run[0]["rvol"] < 1.5:
            return None
        price = float(c["close"])
        if all(b["bull"] for b in run) and max(run[0]["rsi"], c["rsi"]) > 85 and c["low"] > c["bb_upper"]:
            return self.make(PE, price, float(c["high"]), target=float(c["bb_mid"]), note="parabolic up exhaustion")
        if all(b["bear"] for b in run) and min(run[0]["rsi"], c["rsi"]) < 15 and c["high"] < c["bb_lower"]:
            return self.make(CE, price, float(c["low"]), target=float(c["bb_mid"]), note="parabolic down exhaustion")
        return None


class GapAndGo31(Spec):
    sid, name, category = "SENSEX_GAP_GO_31", "Unfilled Gap Continuation", TREND
    start, end, time_exit, max_hold_min = time(10, 20), time(14, 45), time(15, 15), ALL_DAY
    prem_min, prem_max = 250, 400
    reentry, trail = "yes", "ema21"

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 13:
            return None
        ib = t.iloc[:12]
        ih, il = float(ib["high"].max()), float(ib["low"].min())
        day_open = float(t["open"].iloc[0])
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        gap = (day_open - ctx.pdc) / ctx.pdc
        recent = t.iloc[-7:-1]
        touched_vwap = bool(((recent["low"] <= recent["vwap"] * 1.0005) & (recent["high"] >= recent["vwap"] * 0.9995)).any())
        if c["body_pct"] < 0.5 or not touched_vwap or c["volume"] <= recent["volume"].mean():
            return None
        if gap > 0.006 and day_open > ctx.pdh and t["low"].min() > ctx.pdh and price > ih and p["close"] <= ih and c["bull"]:
            return self.make(CE, price, float(c["vwap"]), rr=3.0, close_stop=True,
                             meta={"gap_edge": ctx.pdh}, key=str(ctx.df.index[-1]), note=f"gap-up {gap:.1%} 60m-high break")
        if gap < -0.006 and day_open < ctx.pdl and t["high"].max() < ctx.pdl and price < il and p["close"] >= il and c["bear"]:
            return self.make(PE, price, float(c["vwap"]), rr=3.0, close_stop=True,
                             meta={"gap_edge": ctx.pdl}, key=str(ctx.df.index[-1]), note=f"gap-down {gap:.1%} 60m-low break")
        return None

    def exit_rule(self, ctx, pos):
        edge = (pos.get("meta") or {}).get("gap_edge")
        c = ctx.last
        if edge is not None and sign(pos["direction"]) * (c["close"] - edge) < 0:
            return "closed inside the gap zone"
        if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0:
            return "closed across VWAP"
        return None


class RvolBreakout32(Spec):
    sid, name, category = "SENSEX_RVOL_BRK_32", "RVOL Micro-Consolidation Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(10, 45), time(13, 30), time(15, 15), 60
    prem_min, prem_max = 150, 300
    trail = "ema9"

    def entry(self, ctx):
        c = ctx.c(0)
        if c["rvol"] <= 2.5 or c["body_pct"] <= 0.7:
            return None
        box = ctx.df.iloc[-5:-1]
        bh, bl = float(box["high"].max()), float(box["low"].min())
        if bh - bl >= 30:
            return None
        price, mid = float(c["close"]), float((c["high"] + c["low"]) / 2)
        if price > bh and c["bull"]:
            return self.make(CE, price, mid, rr=2.0, note=f"{bh - bl:.0f}-pt box break up, RVOL {c['rvol']:.1f}")
        if price < bl and c["bear"]:
            return self.make(PE, price, mid, rr=2.0, note=f"{bh - bl:.0f}-pt box break down, RVOL {c['rvol']:.1f}")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed across 9 EMA" if sign(pos["direction"]) * (c["close"] - c["ema9"]) < 0 else None


class EmaTwist33(Spec):
    sid, name, category = "SENSEX_EMA_TWIST_33", "EMA Ribbon Twist", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    trail = "ema13"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        spread = max(p["ema5"], p["ema13"], p["ema21"]) - min(p["ema5"], p["ema13"], p["ema21"])
        if spread >= 10 or c["rvol"] <= 1.5:
            return None
        price = float(c["close"])
        if c["ema5"] > max(c["ema13"], c["ema21"]) and p["ema5"] <= max(p["ema13"], p["ema21"]) \
                and price > max(c["ema5"], c["ema13"], c["ema21"]):
            return self.make(CE, price, float(c["ema21"]), rr=2.5, close_stop=True, note="EMA 5/13/21 twist up")
        if c["ema5"] < min(c["ema13"], c["ema21"]) and p["ema5"] >= min(p["ema13"], p["ema21"]) \
                and price < min(c["ema5"], c["ema13"], c["ema21"]):
            return self.make(PE, price, float(c["ema21"]), rr=2.5, close_stop=True, note="EMA 5/13/21 twist down")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "5 EMA crossed 13 EMA" if sign(pos["direction"]) * (c["ema5"] - c["ema13"]) < 0 else None


class OpenRejection34(Spec):
    sid, name, category = "SENSEX_OPEN_REJ_34", "First Tick Rejection", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 20), time(9, 45), time(11, 0), 90
    prem_min, prem_max = 250, 400
    trail = "ema9"
    needs = ("first_min",)

    def entry(self, ctx):
        m = ctx.aux.get("first_min")
        if m is None or ctx.n_today > 6:
            return None
        rng = float(m["high"] - m["low"])
        if rng <= 0:
            return None
        c = ctx.c(0)
        price = float(c["close"])
        if ctx.today["rvol"].iloc[0] < 2.0:
            return None  # needs extremely high opening volume
        tol = 0.001 * price
        lv = ctx.levels()
        res = [v for k, v in lv.items() if k in ("PDH", "R1", "R2", "P", "PDC")]
        sup = [v for k, v in lv.items() if k in ("PDL", "S1", "S2", "P", "PDC")]
        upper = float(m["high"] - max(m["open"], m["close"])) / rng
        lower = float(min(m["open"], m["close"]) - m["low"]) / rng
        day_hi, day_lo = float(ctx.today["high"].max()), float(ctx.today["low"].min())
        # the 1-min wick must still be the day's extreme (rejection held)
        if upper > 0.6 and any(abs(m["high"] - r) <= tol for r in res) and price < m["low"] and day_hi <= m["high"]:
            return self.make(PE, price, float(m["high"]), target=float(c["vwap"]), rr_fallback=2.0,
                             note=f"1-min rejection at resistance {m['high']:.0f}")
        if lower > 0.6 and any(abs(m["low"] - s) <= tol for s in sup) and price > m["high"] and day_lo >= m["low"]:
            return self.make(CE, price, float(m["low"]), target=float(c["vwap"]), rr_fallback=2.0,
                             note=f"1-min rejection at support {m['low']:.0f}")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "crossed 5-min 9 EMA" if sign(pos["direction"]) * (c["close"] - c["ema9"]) < 0 else None


class FractalBreakout35(Spec):
    sid, name, category = "SENSEX_FRACTAL_BRK_35", "Fractal Breakout", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    reentry, trail = "setup", "ema21"

    def entry(self, ctx):
        df = ctx.df.tail(30)
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        ups, dns = pivots(df.iloc[:-1], "high"), pivots(df.iloc[:-1], "low")
        if price > c["ema21"] and c["ema21"] > ctx.c(3)["ema21"] and ups and dns:
            i = ups[-1]
            fh = float(df["high"].iloc[i])
            if (df["close"].iloc[i + 1:-1] <= fh).all() and p["close"] <= fh < price:
                stop = float(df["low"].iloc[dns[-1]])
                return self.make(CE, price, stop, rr=2.0, key=str(df.index[i]), note=f"up-fractal {fh:.0f} break")
        if price < c["ema21"] and c["ema21"] < ctx.c(3)["ema21"] and ups and dns:
            i = dns[-1]
            fl = float(df["low"].iloc[i])
            if (df["close"].iloc[i + 1:-1] >= fl).all() and p["close"] >= fl > price:
                stop = float(df["high"].iloc[ups[-1]])
                return self.make(PE, price, stop, rr=2.0, key=str(df.index[i]), note=f"down-fractal {fl:.0f} break")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed across 21 EMA" if sign(pos["direction"]) * (c["close"] - c["ema21"]) < 0 else None


class VolumeDryUp36(Spec):
    sid, name, category = "SENSEX_VOL_DRY_36", "Volume Dry-Up Pullback", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350
    reentry, trail = "yes", "ema9"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        price, vw = float(c["close"]), float(c["vwap"])
        for n in (3, 4, 5):
            pull = ctx.df.iloc[-1 - n:-1]
            if len(pull) < n or ctx.n_today < n + 6:
                continue
            vols = pull["volume"].to_numpy()
            if not (np.diff(vols) < 0).all() or c["volume"] <= ctx.df["volume"].iloc[-4:-1].max():
                continue
            before = ctx.df.iloc[-2 - n]
            closes = pull["close"].to_numpy()
            if (np.diff(closes) < 0).sum() >= n - 1 and before["close"] > before["vwap"] and before["ema9"] > before["ema21"] \
                    and c["low"] <= vw * 1.0008 and price > vw and is_bull_engulfing(c, p):
                tgt = float(ctx.df["high"].iloc[-2 - n - 6:-1 - n].max())
                return self.make(CE, price, vw, target=tgt, close_stop=True, note=f"{n}-bar dry-up pullback to VWAP")
            if (np.diff(closes) > 0).sum() >= n - 1 and before["close"] < before["vwap"] and before["ema9"] < before["ema21"] \
                    and c["high"] >= vw * 0.9992 and price < vw and is_bear_engulfing(c, p):
                tgt = float(ctx.df["low"].iloc[-2 - n - 6:-1 - n].min())
                return self.make(PE, price, vw, target=tgt, close_stop=True, note=f"{n}-bar dry-up rally to VWAP")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed across VWAP" if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0 else None


class BreadthDivergence37(Spec):
    sid, name, category = "SENSEX_TICK_DIV_37", "Internal Breadth Divergence", REVERSAL
    start, end, time_exit, max_hold_min = time(10, 15), time(14, 45), time(15, 0), 120
    trail = "ema21"
    needs = ("breadth",)

    def entry(self, ctx):
        ad = ctx.aux.get("breadth")
        if ad is None or len(ad) < 8:
            return None
        ad = ad[ad.index <= ctx.df.index[-1]]
        t = ctx.today
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if len(t) < 8 or len(ad) < 8:
            return None
        recent = t.iloc[-3:-1]
        earlier = t.iloc[:-3]
        ad_recent = ad.reindex(recent.index).max()
        ad_earlier = ad.reindex(earlier.index).max()
        hod = float(recent["high"].max())
        if hod > earlier["high"].max() and ad_recent < ad_earlier and float(recent["rvol"].max()) < 1.2 \
                and c["bear"] and (is_bear_engulfing(c, p) or is_bear_pin(c, 0.5) or c["body_pct"] > 0.6):
            return self.make(PE, price, hod + 10, target=float(c["vwap"]), note="new HOD, breadth lower high")
        lod = float(recent["low"].min())
        ad_r_lo, ad_e_lo = ad.reindex(recent.index).min(), ad.reindex(earlier.index).min()
        if lod < earlier["low"].min() and ad_r_lo > ad_e_lo and float(recent["rvol"].max()) < 1.2 \
                and c["bull"] and (is_bull_engulfing(c, p) or is_bull_pin(c, 0.5) or c["body_pct"] > 0.6):
            return self.make(CE, price, lod - 10, target=float(c["vwap"]), note="new LOD, breadth higher low")
        return None

    def exit_rule(self, ctx, pos):
        ad = ctx.aux.get("breadth")
        if ad is None or len(ad) < 2:
            return None
        prev, now = float(ad.iloc[-2]), float(ad.iloc[-1])
        if pos["direction"] == PE and prev <= 1.0 < now:
            return "A/D crossed above 1.0"
        if pos["direction"] == CE and prev >= 1.0 > now:
            return "A/D crossed below 1.0"
        return None


class Nr7Breakout38(Spec):
    sid, name, category = "SENSEX_NR7_BRK_38", "NR7 Contraction Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 150, 300
    reentry, trail = "setup", "ema9"

    def entry(self, ctx):
        c, nr = ctx.c(0), ctx.c(1)
        last7 = ctx.df["range"].iloc[-8:-1]
        if len(last7) < 7 or nr["range"] > last7.min() or c["rvol"] <= 1.5 or c["body_pct"] < 0.5:
            return None
        price = float(c["close"])
        key = str(ctx.df.index[-2])
        if price > nr["high"] and c["bull"]:
            return self.make(CE, price, float(nr["low"]), rr=3.0, key=key, note=f"NR7 {nr['range']:.0f}-pt break up")
        if price < nr["low"] and c["bear"]:
            return self.make(PE, price, float(nr["high"]), rr=3.0, key=key, note=f"NR7 {nr['range']:.0f}-pt break down")
        return None


class GammaSqueeze39(Spec):
    sid, name, category = "SENSEX_GAMMA_SQR_39", "Post-2 PM Gamma Squeeze", BREAKOUT
    start, end, time_exit, max_hold_min = time(14, 0), time(15, 5), time(15, 25), 30
    prem_min, prem_max = 50, 150
    expiry_rule, capital_pct = "0dte", 0.05
    trail_kind, uses_3min = "price", True
    needs = ("oi",)

    def entry(self, ctx):
        oi = ctx.aux.get("oi")
        if not ctx.is_expiry_day or not oi or not oi.get("CE") or not oi.get("PE"):
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["body_pct"] <= 0.8 or c["rvol"] <= 2.0:
            return None
        call_wall = max(oi["CE"], key=oi["CE"].get)
        put_wall = max(oi["PE"], key=oi["PE"].get)
        if c["bull"] and p["close"] <= call_wall < price:
            return self.make(CE, price, float(c["low"]), prem_sl=0.30, prem_target=0.90,
                             note=f"broke call-OI wall {call_wall:.0f}")
        if c["bear"] and p["close"] >= put_wall > price:
            return self.make(PE, price, float(c["high"]), prem_sl=0.30, prem_target=0.90,
                             note=f"broke put-OI wall {put_wall:.0f}")
        return None

    def exit_rule(self, ctx, pos):
        return "momentum stopped (inside bar)" if is_inside(ctx.c(0), ctx.c(1)) else None


class GapFillReversal40(Spec):
    sid, name, category = "SENSEX_GAP_FILL_REV_40", "Gap Fill Reversal", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), ALL_DAY
    prem_min, prem_max = 250, 350
    trail = "ema21"

    def entry(self, ctx):
        t = ctx.today
        c, p = ctx.c(0), ctx.c(1)
        price, pdc = float(c["close"]), ctx.pdc
        day_open = float(t["open"].iloc[0])
        tol = 0.0002 * price
        if len(t) < 7 or c["rvol"] < 1.5 or not (is_doji(c, 0.15) or is_bull_pin(c) or is_bear_pin(c)):
            return None
        hi, lo = ctx.day_high_low()
        if day_open > pdc * 1.003 and c["low"] <= pdc + tol and price > pdc and t["low"].iloc[:-1].min() > pdc + tol:
            tgt = float(c["vwap"]) if c["vwap"] > price else hi
            return self.make(CE, price, pdc - 25, target=tgt, note=f"gap-up filled to PDC {pdc:.0f}, bounce")
        if day_open < pdc * 0.997 and c["high"] >= pdc - tol and price < pdc and t["high"].iloc[:-1].max() < pdc - tol:
            tgt = float(c["vwap"]) if c["vwap"] < price else lo
            return self.make(PE, price, pdc + 25, target=tgt, note=f"gap-down filled to PDC {pdc:.0f}, reject")
        return None

    def exit_rule(self, ctx, pos):
        if sign(pos["direction"]) * (float(ctx.last["close"]) - ctx.pdc) < -20:
            return "closed >20 pts beyond PDC"
        return None


# ============================================================ 41-60
class AnchoredVwap41(Spec):
    sid, name, category = "SENSEX_AVWAP_41", "Anchored VWAP Bounce", TREND
    start, end, time_exit, max_hold_min = time(9, 50), time(14, 45), time(15, 0), 120
    reentry, trail = "yes", "ema9"

    @staticmethod
    def _avwap(ctx, d):
        first = ctx.today.iloc[:3]
        if len(first) < 3:
            return None
        ts = first["low"].idxmin() if d == CE else first["high"].idxmax()
        return anchored_vwap(ctx.today[ctx.today.index >= ts]), str(ts)

    def entry(self, ctx):
        if ctx.n_today < 8:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        prior = ctx.df.iloc[-4:-1]
        if not (prior["volume"].mean() < c["vol_avg20"] and c["volume"] > prior["volume"].mean()):
            return None
        for d in (CE, PE):
            res = self._avwap(ctx, d)
            if res is None:
                continue
            av, anchor = res
            above = (ctx.today["close"].iloc[3:-1] > av).mean()
            if d == CE and above >= 0.7 and c["low"] <= av * 1.0005 and price > av and rev_up(c, p):
                return self.make(CE, price, min(av, float(c["low"])), rr=2.0, close_stop=True,
                                 meta={"anchor": anchor}, note=f"AVWAP {av:.0f} bounce")
            if d == PE and above <= 0.3 and c["high"] >= av * 0.9995 and price < av and rev_dn(c, p):
                return self.make(PE, price, max(av, float(c["high"])), rr=2.0, close_stop=True,
                                 meta={"anchor": anchor}, note=f"AVWAP {av:.0f} rejection")
        return None

    def exit_rule(self, ctx, pos):
        anchor = (pos.get("meta") or {}).get("anchor")
        if not anchor:
            return None
        av = anchored_vwap(ctx.today[ctx.today.index >= pd.Timestamp(anchor)])
        if sign(pos["direction"]) * (float(ctx.last["close"]) - av) < 0:
            return f"closed across AVWAP {av:.0f}"
        return None


class InitialBalance42(Spec):
    sid, name, category = "SENSEX_IB_EXT_42", "Initial Balance Extension", BREAKOUT
    start, end, time_exit, max_hold_min = time(10, 20), time(14, 45), time(15, 15), ALL_DAY
    delta_target, delta_min, delta_max = 0.45, 0.38, 0.52
    prem_min, prem_max = 150, 350
    trail = "vwap"

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 13:
            return None
        ib = t.iloc[:12]
        ih, il = float(ib["high"].max()), float(ib["low"].min())
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if (ih - il) / price > 0.009 or c["rvol"] <= 1.5 or c["body_pct"] < 0.6:
            return None
        meta = {"ib_mid": (ih + il) / 2}
        if price > ih and p["close"] <= ih and c["bull"]:
            return self.make(CE, price, float(c["low"]), rr=3.0, meta=meta, note=f"IB {il:.0f}-{ih:.0f} up-extension")
        if price < il and p["close"] >= il and c["bear"]:
            return self.make(PE, price, float(c["high"]), rr=3.0, meta=meta, note=f"IB {il:.0f}-{ih:.0f} down-extension")
        return None

    def exit_rule(self, ctx, pos):
        mid = (pos.get("meta") or {}).get("ib_mid")
        if mid is not None and sign(pos["direction"]) * (float(ctx.last["close"]) - mid) < 0:
            return "back inside IB past midpoint"
        return None


class PocBounce43(Spec):
    sid, name, category = "SENSEX_POC_BNC_43", "Previous Day POC Bounce", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 400
    trail = "ema21"

    @staticmethod
    def poc(ctx, bin_pts: float = 20.0) -> Optional[float]:
        prev = ctx.df[ctx.df.index.date < ctx.today_date]
        if prev.empty:
            return None
        prev = prev[prev.index.date == prev.index[-1].date()]
        vol = prev["volume"].astype(float)
        if vol.sum() <= 0:
            return None
        tp = (prev["high"] + prev["low"] + prev["close"]) / 3
        bins = (tp / bin_pts).round() * bin_pts
        return float(vol.groupby(bins).sum().idxmax())

    def entry(self, ctx):
        poc = self.poc(ctx)
        if poc is None or ctx.n_today < 3:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price, tol = float(c["close"]), 0.0003 * float(c["close"])
        if c["rvol"] <= 1.5:
            return None
        if c["low"] <= poc + tol and price > poc and p["close"] > poc and is_bull_pin(c, 0.5):
            return self.make(CE, price, poc - 20, target=ctx.pdh, note=f"prev-day POC {poc:.0f} bounce")
        if c["high"] >= poc - tol and price < poc and p["close"] < poc and is_bear_pin(c, 0.5):
            return self.make(PE, price, poc + 20, target=ctx.pdl, note=f"prev-day POC {poc:.0f} rejection")
        return None


class DoubleInsideBar44(Spec):
    sid, name, category = "SENSEX_DIB_44", "Double Inside Bar Breakout", BREAKOUT
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 60
    prem_min, prem_max = 200, 350
    trail = "ema9"

    def entry(self, ctx):
        c, i1, i2, m = ctx.c(0), ctx.c(1), ctx.c(2), ctx.c(3)
        if not (is_inside(i2, m) and is_inside(i1, m) and is_inside(i1, i2)):
            return None
        if c["volume"] <= i1["volume"] + i2["volume"]:
            return None
        price, mid = float(c["close"]), float((m["high"] + m["low"]) / 2)
        meta = {"mother_high": float(m["high"]), "mother_low": float(m["low"])}
        if price > m["high"]:
            return self.make(CE, price, mid, rr=2.5, meta=meta, note="double inside bar break up")
        if price < m["low"]:
            return self.make(PE, price, mid, rr=2.5, meta=meta, note="double inside bar break down")
        return None

    def exit_rule(self, ctx, pos):
        m = pos.get("meta") or {}
        c = float(ctx.last["close"])
        if pos["direction"] == CE and m.get("mother_high") and c < m["mother_high"]:
            return "back inside mother bar"
        if pos["direction"] == PE and m.get("mother_low") and c > m["mother_low"]:
            return "back inside mother bar"
        return None


class OrderBlock45(Spec):
    sid, name, category = "SENSEX_OB_TEST_45", "Order Block Retest", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 180
    trail = "ema21"

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 10:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["rvol"] < 1.3:
            return None
        hist = t.iloc[:-1]
        for d in (CE, PE):
            # most recent impulse: >= 0.4% move within 4 candles, preceded by an opposite candle
            for j in range(len(hist) - 5, 0, -1):
                ob = hist.iloc[j]
                imp = hist.iloc[j + 1:j + 5]
                if d == CE and ob["bear"] and imp["high"].max() - ob["low"] >= 0.004 * price:
                    zone_hi, zone_lo = float(ob["high"]), float(ob["low"])
                    k = j + 1 + int(np.argmax(imp["high"].to_numpy()))
                    after = hist.iloc[k + 1:]
                    if after.empty or (after["low"] <= zone_hi).any():
                        break  # already tapped (first tap only)
                    if c["low"] <= zone_hi and price > zone_hi and is_bull_engulfing(c, p):
                        return self.make(CE, price, zone_lo - 5, target=float(hist["high"].iloc[k:].max()),
                                         note=f"bullish OB {zone_lo:.0f}-{zone_hi:.0f} first tap")
                    break
                if d == PE and ob["bull"] and ob["high"] - imp["low"].min() >= 0.004 * price:
                    zone_hi, zone_lo = float(ob["high"]), float(ob["low"])
                    k = j + 1 + int(np.argmin(imp["low"].to_numpy()))
                    after = hist.iloc[k + 1:]
                    if after.empty or (after["high"] >= zone_lo).any():
                        break
                    if c["high"] >= zone_lo and price < zone_lo and is_bear_engulfing(c, p):
                        return self.make(PE, price, zone_hi + 5, target=float(hist["low"].iloc[k:].min()),
                                         note=f"bearish OB {zone_lo:.0f}-{zone_hi:.0f} first tap")
                    break
        return None

    def exit_rule(self, ctx, pos):
        return None  # "close beyond the OB" is the price stop just past the zone


class VwapSlingshot46(Spec):
    sid, name, category = "SENSEX_SLING_46", "VWAP Slingshot", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 60
    delta_target, delta_min, delta_max = 0.40, 0.33, 0.47
    prem_min, prem_max = 150, 300
    trail = "ema9"

    def entry(self, ctx):
        if ctx.n_today < 8:
            return None
        c, p, q = ctx.c(0), ctx.c(1), ctx.c(2)
        price = float(c["close"])
        side = np.sign(ctx.today["close"].iloc[-13:-2] - ctx.today["vwap"].iloc[-13:-2])
        up_trend = side.mean() > 0.6 and c["ema21"] > ctx.c(6)["ema21"]
        dn_trend = side.mean() < -0.6 and c["ema21"] < ctx.c(6)["ema21"]
        if c["volume"] <= p["volume"] or p["rvol"] >= 1.0:
            return None
        if up_trend and q["close"] > q["vwap"] and p["close"] < p["vwap"] and price > c["vwap"] and is_bull_engulfing(c, p):
            return self.make(CE, price, float(min(p["low"], c["low"])), rr=2.0, note="VWAP fake breakdown slingshot")
        if dn_trend and q["close"] < q["vwap"] and p["close"] > p["vwap"] and price < c["vwap"] and is_bear_engulfing(c, p):
            return self.make(PE, price, float(max(p["high"], c["high"])), rr=2.0, note="VWAP fake breakout slingshot")
        return None

    def exit_rule(self, ctx, pos):
        return self.no_new_extreme(ctx, pos, 3)


class HiddenDivergence47(Spec):
    sid, name, category = "SENSEX_HDIV_47", "RSI Hidden Divergence", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 450
    reentry, trail = "setup", "ema21"

    def entry(self, ctx):
        df = ctx.df.tail(40)
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if len(df) < 20:
            return None
        rec = df.iloc[-3:]
        if is_bull_engulfing(c, p) and c["ema21"] > ctx.c(5)["ema21"]:
            l2 = float(rec["low"].min())
            r2 = float(rec["rsi"].min())
            if l2 <= df["low"].iloc[-8:-3].min():
                piv = [i for i in pivots(df.iloc[:-6], "low")]
                if piv:
                    i = piv[-1]
                    l1, r1 = float(df["low"].iloc[i]), float(df["rsi"].iloc[i])
                    if l2 > l1 and r2 < r1:
                        tgt = float(df["high"].iloc[i:-3].max())
                        return self.make(CE, price, l2, target=tgt, rr_fallback=2.0, key=str(df.index[i]),
                                         note=f"hidden bull div: HL {l1:.0f}->{l2:.0f}, RSI {r1:.0f}->{r2:.0f}")
        if is_bear_engulfing(c, p) and c["ema21"] < ctx.c(5)["ema21"]:
            h2 = float(rec["high"].max())
            r2 = float(rec["rsi"].max())
            if h2 >= df["high"].iloc[-8:-3].max():
                piv = [i for i in pivots(df.iloc[:-6], "high")]
                if piv:
                    i = piv[-1]
                    h1, r1 = float(df["high"].iloc[i]), float(df["rsi"].iloc[i])
                    if h2 < h1 and r2 > r1:
                        tgt = float(df["low"].iloc[i:-3].min())
                        return self.make(PE, price, h2, target=tgt, rr_fallback=2.0, key=str(df.index[i]),
                                         note=f"hidden bear div: LH {h1:.0f}->{h2:.0f}, RSI {r1:.0f}->{r2:.0f}")
        return None

    def exit_rule(self, ctx, pos):
        c, p = ctx.c(0), ctx.c(1)
        if pos["direction"] == CE and p["rsi"] >= 50 > c["rsi"]:
            return "RSI crossed below 50"
        if pos["direction"] == PE and p["rsi"] <= 50 < c["rsi"]:
            return "RSI crossed above 50"
        return None


class OiWall48(Spec):
    sid, name, category = "SENSEX_OI_WALL_48", "Open Interest Wall Reject", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350
    trail = "ema9"
    needs = ("oi",)

    @staticmethod
    def walls(side: dict) -> list[float]:
        ks = sorted(side)
        out = []
        for i, k in enumerate(ks):
            nb = [side[ks[j]] for j in (i - 1, i + 1) if 0 <= j < len(ks)]
            if nb and side[k] > 2 * (sum(nb) / len(nb)):
                out.append(k)
        return out

    def entry(self, ctx):
        oi = ctx.aux.get("oi")
        if not oi or not oi.get("CE") or not oi.get("PE"):
            return None
        c = ctx.c(0)
        price = float(c["close"])
        tol = 0.0005 * price
        if c["rvol"] <= 1.5:
            return None
        for k in self.walls(oi["CE"]):
            if c["high"] >= k - tol and price < k and is_bear_pin(c, 0.5):
                return self.make(PE, price, k + 30, target=float(c["vwap"]), meta={"wall": k},
                                 note=f"rejected call-OI wall {k:.0f}")
        for k in self.walls(oi["PE"]):
            if c["low"] <= k + tol and price > k and is_bull_pin(c, 0.5):
                return self.make(CE, price, k - 30, target=float(c["vwap"]), meta={"wall": k},
                                 note=f"rejected put-OI wall {k:.0f}")
        return None

    def exit_rule(self, ctx, pos):
        k = (pos.get("meta") or {}).get("wall")
        bars = bars_since_entry(ctx, pos)
        if k and len(bars) >= 3 and (abs(bars["close"].iloc[-3:] - k) <= 0.001 * k).all():
            return "stalled at the OI wall for 15 min"
        return None


class TripleEmaAlign49(Spec):
    sid, name, category = "SENSEX_TEMA_ALIGN_49", "Triple EMA Alignment", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 450
    reentry, trail = "yes", "ema21"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["body_pct"] < 0.5:
            return None
        fan = 0.0005 * price
        if c["ema8"] > c["ema13"] > c["ema21"] and p["ema8"] > p["ema13"] > p["ema21"] and c["ema8"] - c["ema21"] > fan \
                and p["low"] <= p["ema8"] and p["close"] >= p["ema13"] and c["bull"] and price > c["ema8"]:
            return self.make(CE, price, float(c["ema21"]), rr=2.0, close_stop=True, note="8>13>21 stack pullback")
        if c["ema8"] < c["ema13"] < c["ema21"] and p["ema8"] < p["ema13"] < p["ema21"] and c["ema21"] - c["ema8"] > fan \
                and p["high"] >= p["ema8"] and p["close"] <= p["ema13"] and c["bear"] and price < c["ema8"]:
            return self.make(PE, price, float(c["ema21"]), rr=2.0, close_stop=True, note="8<13<21 stack pullback")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "8 EMA crossed 13 EMA" if sign(pos["direction"]) * (c["ema8"] - c["ema13"]) < 0 else None


class EuropeanOpen50(Spec):
    sid, name, category = "SENSEX_TOD_REV_50", "European Open Reversal", REVERSAL
    start, end, time_exit, max_hold_min = time(12, 30), time(13, 15), time(15, 0), 120
    delta_target, delta_min, delta_max = 0.45, 0.38, 0.52
    prem_min, prem_max = 150, 300
    trail = "ema21"
    needs = ("daily",)

    def entry(self, ctx):
        daily = ctx.aux.get("daily")
        if daily is None or len(daily) < 10:
            return None
        adr = float((daily["high"] - daily["low"]).tail(10).mean())
        hi, lo = ctx.day_high_low()
        if hi - lo < 0.8 * adr:
            return None  # morning trend has not reached its ADR
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        day_open = float(ctx.today["open"].iloc[0])
        if c["rvol"] < 1.5:
            return None
        if price > day_open and c["rsi"] > 70 or (p["rsi"] > 70 and price > day_open):
            if rev_dn(c, p):
                return self.make(PE, price, float(max(c["high"], p["high"])), target=float(c["vwap"]),
                                 note="European-open reversal of up morning")
        if price < day_open and c["rsi"] < 30 or (p["rsi"] < 30 and price < day_open):
            if rev_up(c, p):
                return self.make(CE, price, float(min(c["low"], p["low"])), target=float(c["vwap"]),
                                 note="European-open reversal of down morning")
        return None


class EodImbalance51(Spec):
    sid, name, category = "SENSEX_EOD_IMB_51", "End of Day Imbalance Scalp", BREAKOUT
    start, end, time_exit, max_hold_min = time(15, 10), time(15, 10), time(15, 25), 20
    delta_target, delta_min, delta_max = 0.60, 0.53, 0.67
    prem_min, prem_max = 300, 500
    expiry_rule, capital_pct = "next", 0.05
    trail_kind, uses_3min = "price", True

    def entry(self, ctx):
        c, b = ctx.c(0), ctx.c(1)
        if ctx.df.index[-2].time() != time(15, 0) or b["rvol"] < 1.2:
            return None
        price, mid = float(c["close"]), float((b["high"] + b["low"]) / 2)
        if price > b["high"]:
            return self.make(CE, price, mid, note="15:05 broke 15:00 high")
        if price < b["low"]:
            return self.make(PE, price, mid, note="15:05 broke 15:00 low")
        return None


class DoubleLiquidity52(Spec):
    sid, name, category = "SENSEX_DBL_LIQ_52", "Double Bottom/Top Liquidity Grab", REVERSAL
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 120
    trail = "ema9"

    def entry(self, ctx):
        df = ctx.df.tail(40)
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        sweep = df.iloc[-2:]
        top_vol = float(df["volume"].iloc[-10:].max())
        if float(sweep["volume"].max()) < top_vol:
            return None
        for i in reversed(pivots(df.iloc[:-6], "low")):
            l1 = float(df["low"].iloc[i])
            swept = float(sweep["low"].min())
            if l1 * 0.9985 <= swept < l1 and (df["low"].iloc[i + 1:-2] > l1).all() and price > l1 and is_bull_engulfing(c, p):
                neck = float(df["high"].iloc[i + 1:-2].max())
                return self.make(CE, price, swept, target=neck, note=f"double-bottom sweep of {l1:.0f}")
            break
        for i in reversed(pivots(df.iloc[:-6], "high")):
            h1 = float(df["high"].iloc[i])
            swept = float(sweep["high"].max())
            if h1 < swept <= h1 * 1.0015 and (df["high"].iloc[i + 1:-2] < h1).all() and price < h1 and is_bear_engulfing(c, p):
                neck = float(df["low"].iloc[i + 1:-2].min())
                return self.make(PE, price, swept, target=neck, note=f"double-top sweep of {h1:.0f}")
            break
        return None


class SqueezeMomentum53(Spec):
    sid, name, category = "SENSEX_TTM_MOM_53", "Squeeze Momentum Ignition", BREAKOUT
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 200, 350
    trail = "ema9"

    def entry(self, ctx):
        c, p = ctx.c(0), ctx.c(1)
        if np.isnan(c["ttm_mom"]) or np.isnan(p["ttm_mom"]) or c["rvol"] < 1.2:
            return None
        fired = bool(ctx.df["squeeze_on"].iloc[-3:-1].any()) and not bool(c["squeeze_on"])
        if not fired:
            return None
        price = float(c["close"])
        if p["ttm_mom"] <= 0 < c["ttm_mom"] and price > c["kc_upper"]:
            return self.make(CE, price, float(c["sma20"]), close_stop=True, note="squeeze fired, momentum up")
        if p["ttm_mom"] >= 0 > c["ttm_mom"] and price < c["kc_lower"]:
            return self.make(PE, price, float(c["sma20"]), close_stop=True, note="squeeze fired, momentum down")
        return None

    def exit_rule(self, ctx, pos):
        c, p = ctx.c(0), ctx.c(1)
        if sign(pos["direction"]) * (c["ttm_mom"] - p["ttm_mom"]) < 0:
            return "momentum histogram fading"
        return None


class FlagBreakout54(Spec):
    sid, name, category = "SENSEX_FLAG_BRK_54", "Flag/Pennant Continuation", TREND
    start, end, time_exit, max_hold_min = time(9, 45), time(14, 45), time(15, 15), 120
    prem_min, prem_max = 250, 400
    trail = "ema9"

    def entry(self, ctx):
        df = ctx.df.tail(25)
        c = ctx.c(0)
        price = float(c["close"])
        hist = df.iloc[:-1]
        for flag_len in range(3, 11):
            flag = hist.iloc[-flag_len:]
            pole = hist.iloc[-flag_len - 6:-flag_len]
            if len(pole) < 3:
                break
            for d in (CE, PE):
                if d == CE:
                    top, base = float(pole["high"].max()), float(pole["low"].min())
                    height = top - base
                    if height < 0.005 * price or pole["high"].iloc[-2:].max() < top:
                        continue  # pole must end at its high
                    if flag["low"].min() < top - 0.5 * height or flag["high"].max() > top:
                        continue
                    x = np.arange(len(flag))
                    slope, icpt = np.polyfit(x, flag["high"].to_numpy(), 1)
                    line = icpt + slope * len(flag)
                    ok = slope <= 0 and price > line and c["bull"]
                    stop = float(flag["low"].min())
                else:
                    top, base = float(pole["low"].min()), float(pole["high"].max())
                    height = base - top
                    if height < 0.005 * price or pole["low"].iloc[-2:].min() > top:
                        continue
                    if flag["high"].max() > top + 0.5 * height or flag["low"].min() < top:
                        continue
                    x = np.arange(len(flag))
                    slope, icpt = np.polyfit(x, flag["low"].to_numpy(), 1)
                    line = icpt + slope * len(flag)
                    ok = slope >= 0 and price < line and c["bear"]
                    stop = float(flag["high"].max())
                if not ok:
                    continue
                if not (flag["volume"].mean() < pole["volume"].mean() and c["volume"] > flag["volume"].mean()):
                    continue
                return self.make(d, price, stop, target=price + sign(d) * height, meta={"flag_line": float(line)},
                                 note=f"{'bull' if d == CE else 'bear'} flag break, pole {height:.0f} pts")
        return None

    def exit_rule(self, ctx, pos):
        line = (pos.get("meta") or {}).get("flag_line")
        if line is not None and sign(pos["direction"]) * (float(ctx.last["close"]) - line) < 0:
            return "closed back inside the flag"
        return None


class MultiTimeframe55(Spec):
    sid, name, category = "SENSEX_MTF_ALIGN_55", "Multi-Timeframe Alignment", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 180
    prem_min, prem_max = 250, 450
    reentry, trail = "yes", "ema21"

    @staticmethod
    def h1_bias(ctx) -> int:
        d = ctx.df[["open", "high", "low", "close"]]
        h = d.resample("60min", origin="start_day", offset="15min").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        h = h[h.index + pd.Timedelta(minutes=60) <= ctx.df.index[-1] + pd.Timedelta(minutes=5)]
        if len(h) < 12:
            return 0
        e = h["close"].ewm(span=9, adjust=False).mean()
        return 1 if h["close"].iloc[-1] > e.iloc[-1] else -1

    def entry(self, ctx):
        if ctx.df15 is None or len(ctx.df15) < 30:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        l15 = ctx.df15.iloc[-1]
        b15 = 1 if l15["close"] > l15["ema9"] else -1
        b60 = self.h1_bias(ctx)
        if b15 != b60 or b60 == 0:
            return None
        pull = ctx.df.iloc[-6:-1]
        if b60 > 0 and p["close"] < p["ema9"] and price > c["ema9"] and is_bull_engulfing(c, p):
            return self.make(CE, price, float(pull["low"].min()), rr=3.0, note="5m/15m/60m aligned up")
        if b60 < 0 and p["close"] > p["ema9"] and price < c["ema9"] and is_bear_engulfing(c, p):
            return self.make(PE, price, float(pull["high"].max()), rr=3.0, note="5m/15m/60m aligned down")
        return None

    def exit_rule(self, ctx, pos):
        if ctx.df15 is None or ctx.df15.empty:
            return None
        l15 = ctx.df15.iloc[-1]
        if sign(pos["direction"]) * (l15["close"] - l15["ema9"]) < 0:
            return "15m closed across 15m 9 EMA"
        return None


class FibConfluence56(Spec):
    sid, name, category = "SENSEX_FIB_CONFL_56", "Fib 38.2 + 50 EMA Confluence", TREND
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 180
    delta_target, delta_min, delta_max = 0.55, 0.48, 0.62
    prem_min, prem_max = 250, 450
    trail = "ema21"

    def entry(self, ctx):
        df = ctx.df.tail(40)
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["volume"] <= c["vol_avg20"]:
            return None
        hist = df.iloc[:-2]
        for d in (CE, PE):
            if d == CE:
                k = int(np.argmax(hist["high"].to_numpy()))
                ext = float(hist["high"].iloc[k])
                origin = float(hist["low"].iloc[: k + 1].min()) if k > 0 else None
            else:
                k = int(np.argmin(hist["low"].to_numpy()))
                ext = float(hist["low"].iloc[k])
                origin = float(hist["high"].iloc[: k + 1].max()) if k > 0 else None
            if origin is None or abs(ext - origin) < 0.004 * price:
                continue
            size = abs(ext - origin)
            f382, f50 = ext - sign(d) * 0.382 * size, ext - sign(d) * 0.5 * size
            pull = df.iloc[k + 1:]
            e50 = float(c["ema50"])
            if abs(f382 - e50) > 0.001 * price:
                continue
            if d == CE and pull["low"].min() > f50 and c["low"] <= max(f382, e50) and price > max(f382, e50) \
                    and is_bull_pin(c, 0.5):
                return self.make(CE, price, f50 - 5, target=ext, note=f"38.2% {f382:.0f} + EMA50 {e50:.0f}")
            if d == PE and pull["high"].max() < f50 and c["high"] >= min(f382, e50) and price < min(f382, e50) \
                    and is_bear_pin(c, 0.5):
                return self.make(PE, price, f50 + 5, target=ext, note=f"38.2% {f382:.0f} + EMA50 {e50:.0f}")
        return None


class VwapPinch57(Spec):
    sid, name, category = "SENSEX_VWAP_PINCH_57", "VWAP Pinch Squeeze", BREAKOUT
    start, end, time_exit, max_hold_min = time(11, 0), time(14, 45), time(15, 15), 60
    delta_target, delta_min, delta_max = 0.45, 0.38, 0.52
    prem_min, prem_max = 150, 300
    trail = "ema9"

    def entry(self, ctx):
        c = ctx.c(0)
        box = ctx.df.iloc[-7:-1]
        if len(box) < 6 or c["rvol"] <= 2.0 or c["body_pct"] < 0.8:
            return None
        bh, bl = float(box["high"].max()), float(box["low"].min())
        chops = ((box["low"] <= box["vwap"]) & (box["high"] >= box["vwap"])).all()
        if not chops or bh - bl > 15:
            return None
        price = float(c["close"])
        if c["low"] > c["vwap"] and c["bull"]:
            return self.make(CE, price, bl, rr=2.5, note=f"VWAP pinch {bl:.0f}-{bh:.0f} break up")
        if c["high"] < c["vwap"] and c["bear"]:
            return self.make(PE, price, bh, rr=2.5, note=f"VWAP pinch {bl:.0f}-{bh:.0f} break down")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "closed back over VWAP" if sign(pos["direction"]) * (c["close"] - c["vwap"]) < 0 else None


class OpeningLowSweep58(Spec):
    sid, name, category = "SENSEX_PREM_LOW_58", "Opening Low Sweep", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 25), time(9, 50), time(11, 30), 90
    prem_min, prem_max = 250, 400
    trail = "ema9"

    def entry(self, ctx):
        t = ctx.today
        if len(t) < 3:
            return None
        first = t.iloc[0]
        if first["open"] >= ctx.pdc:
            return None  # gap-down opens only
        lvl = float(first["low"])
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        after = t.iloc[1:]
        below = after[after["low"] < lvl]
        if below.empty or (after["close"] < lvl).sum() > 2 or below.index[0].time() > time(9, 40):
            return None
        if price > lvl and is_bull_engulfing(c, p) and float(below["rvol"].max()) >= 1.5:
            stop = float(after["low"].min())
            return self.make(CE, price, stop, target=float(c["vwap"]), rr_fallback=2.0,
                             note=f"swept opening low {lvl:.0f}")
        return None


class GapExhaustion59(Spec):
    sid, name, category = "SENSEX_GAP_EXH_59", "Exhaustion Gap Fade", REVERSAL
    start, end, time_exit, max_hold_min = time(9, 35), time(12, 0), time(15, 15), 180
    trail = "ema21"
    needs = ("daily",)

    def entry(self, ctx):
        daily = ctx.aux.get("daily")
        t = ctx.today
        if daily is None or len(daily) < 3 or len(t) < 4:
            return None
        last3 = daily.tail(3)
        if not (last3["close"] > last3["open"]).all():
            return None
        day_open = float(t["open"].iloc[0])
        if (day_open - ctx.pdc) / ctx.pdc <= 0.005:
            return None
        first15_hi = float(t["high"].iloc[:3].max())
        if t["high"].iloc[3:].max() > first15_hi if len(t) > 3 else False:
            return None
        prev = ctx.df[ctx.df.index.date < ctx.today_date]
        prev = prev[prev.index.date == prev.index[-1].date()] if not prev.empty else prev
        if prev.empty or t["volume"].iloc[:3].sum() >= prev["volume"].iloc[:3].sum():
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        if c["bear"] and price < c["vwap"] and p["close"] >= p["vwap"]:
            hi, _ = ctx.day_high_low()
            return self.make(PE, price, hi, target=ctx.pdc, note=f"exhaustion gap +{(day_open / ctx.pdc - 1):.1%} fade")
        return None

    def exit_rule(self, ctx, pos):
        c = ctx.last
        return "reclaimed VWAP" if c["close"] > c["vwap"] else None


class NiftyDivergence60(Spec):
    sid, name, category = "SENSEX_MACRO_DIV_60", "Nifty/Sensex Divergence", REVERSAL
    start, end, time_exit, max_hold_min = time(10, 0), time(14, 45), time(15, 15), 120
    trail = "ema9"
    needs = ("nifty",)

    def entry(self, ctx):
        n = ctx.aux.get("nifty")
        t = ctx.today
        if n is None or len(n) < 8 or len(t) < 8:
            return None
        n = n[n.index <= ctx.df.index[-1]]
        if len(n) < 8:
            return None
        c, p = ctx.c(0), ctx.c(1)
        price = float(c["close"])
        n_new_high = n["high"].iloc[-2:].max() > n["high"].iloc[:-2].max()
        n_new_low = n["low"].iloc[-2:].min() < n["low"].iloc[:-2].min()
        s_hi_prior, s_lo_prior = float(t["high"].iloc[:-2].max()), float(t["low"].iloc[:-2].min())
        if n_new_high and t["high"].iloc[-2:].max() < s_hi_prior and rev_dn(c, p):
            return self.make(PE, price, float(c["high"]), target=float(c["vwap"]), meta={"hod": s_hi_prior},
                             note="NIFTY new high, SENSEX lower high")
        if n_new_low and t["low"].iloc[-2:].min() > s_lo_prior and rev_up(c, p):
            return self.make(CE, price, float(c["low"]), target=float(c["vwap"]), meta={"lod": s_lo_prior},
                             note="NIFTY new low, SENSEX higher low")
        return None

    def exit_rule(self, ctx, pos):
        m, c = pos.get("meta") or {}, float(ctx.last["close"])
        if pos["direction"] == PE and m.get("hod") and c > m["hod"]:
            return "SENSEX broke its high"
        if pos["direction"] == CE and m.get("lod") and c < m["lod"]:
            return "SENSEX broke its low"
        return None


STRATEGIES_21_60: list[Strategy] = [
    VwapDeviation21(), OpenDrive22(), PdcBounce23(), OrbFail24(), AtrExpansion25(), LunchFade26(),
    LiquidityGrab27(), VwapPin28(), VixCrush29(), TrendExhaustion30(), GapAndGo31(), RvolBreakout32(),
    EmaTwist33(), OpenRejection34(), FractalBreakout35(), VolumeDryUp36(), BreadthDivergence37(),
    Nr7Breakout38(), GammaSqueeze39(), GapFillReversal40(),
    AnchoredVwap41(), InitialBalance42(), PocBounce43(), DoubleInsideBar44(), OrderBlock45(), VwapSlingshot46(),
    HiddenDivergence47(), OiWall48(), TripleEmaAlign49(), EuropeanOpen50(), EodImbalance51(), DoubleLiquidity52(),
    SqueezeMomentum53(), FlagBreakout54(), MultiTimeframe55(), FibConfluence56(), VwapPinch57(),
    OpeningLowSweep58(), GapExhaustion59(), NiftyDivergence60(),
]
