"""Adaptive Directional Momentum & Volatility Expansion (ADMVE).

This is a research candidate, not a claim of verified profitability. It only emits a
single-leg directional signal after closed-candle confirmation; sizing, option selection,
risk limits, paper/live mode and order execution remain in Engine.
"""
from __future__ import annotations

from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..market import BEAR, BULL, SIDEWAYS
from .base import CE, PE, TREND, Signal, Strategy


class AdaptiveDirectionalMomentum(Strategy):
    sid, name, category = "SENSEX_ADMVE_80", "Adaptive Directional Momentum & Volatility Expansion", TREND
    start, end, time_exit, max_hold_min = time(9, 30), time(14, 30), time(15, 15), 90
    delta_target, delta_min, delta_max = 0.55, 0.45, 0.65
    prem_min, prem_max = 100, 900
    capital_pct = 0.10
    prem_sl_pct = 0.25
    reentry = "setup"                    # one entry per direction + trigger kind per day
    max_entries = 2
    trail_kind = "price"
    needs = ("liquidity", "futures_depth")
    # Score = 70 for passing every mandatory gate + optional evidence (max 100):
    # ATR expansion 10, relative volume 5, room to the next opposing liquidity level 10,
    # SENSEX breadth 5. 80 needs ATR expansion or room, or volume + breadth.
    min_score = 80
    BASE_SCORE = 70
    OPTIONAL_WEIGHTS = {"atr_expansion": 10, "volume": 5, "room": 10, "breadth": 5}

    def entry(self, ctx) -> Optional[Signal]:
        if ctx.n_today < 8 or ctx.df15 is None:
            return None
        # Resampling 5m bars can leave the current 15m bucket partial. Use only
        # 15m candles whose full 15-minute interval has closed.
        last_5m_close = ctx.df.index[-1] + pd.Timedelta(minutes=5)
        df15 = ctx.df15[ctx.df15.index + pd.Timedelta(minutes=15) <= last_5m_close]
        if len(df15) < 30:
            return None
        d = ctx.df
        c, p = d.iloc[-1], d.iloc[-2]
        close, atr = float(c["close"]), float(c["atr"])
        if not np.isfinite(atr) or atr <= 0:
            return None
        # Use only prior completed bars for all breakout/volatility baselines.
        prior6, prior8 = d.iloc[-7:-1], d.iloc[-9:-1]
        if len(prior6) < 6 or len(prior8) < 8:
            return None
        atr_hist = d["atr"].iloc[-21:-1].dropna()
        if len(atr_hist) < 15:
            return None
        atr_ratio = atr / float(atr_hist.median())
        rsi7 = float(ind.rsi(d["close"], 7).iloc[-1])
        l15 = df15.iloc[-1]
        bull15 = float(l15["ema9"]) > float(l15["ema21"]) and float(l15["plus_di"]) > float(l15["minus_di"])
        bear15 = float(l15["ema9"]) < float(l15["ema21"]) and float(l15["minus_di"]) > float(l15["plus_di"])
        adx_rising = float(c["adx"]) > float(p["adx"])
        ema21_rising = float(c["ema21"]) > float(d["ema21"].iloc[-4])
        ema21_falling = float(c["ema21"]) < float(d["ema21"].iloc[-4])
        bull_stack = float(c["ema9"]) > float(c["ema21"]) > float(c["ema50"])
        bear_stack = float(c["ema9"]) < float(c["ema21"]) < float(c["ema50"])
        above_vwap, below_vwap = close > float(c["vwap"]), close < float(c["vwap"])
        body_ok = float(c["body_pct"]) >= 0.55
        close_pos = (close - float(c["low"])) / max(float(c["high"]) - float(c["low"]), 1e-9)
        vol_ok = float(c["rvol"]) >= 1.15
        liq = ctx.aux.get("liquidity") or {}
        liq_score = float(liq.get("score") or 0.0)
        liq_event = liq.get("event", "none")
        liq_direction = int(liq.get("direction") or 0)
        bull_break = close > float(prior6["high"].max()) and body_ok and close_pos >= 0.75 and vol_ok
        bear_break = close < float(prior6["low"].min()) and body_ok and close_pos <= 0.25 and vol_ok
        bull_sweep = liq_event == "bullish_sweep_reclaim" and liq_direction > 0 and close > float(c["vwap"])
        bear_sweep = liq_event == "bearish_sweep_reclaim" and liq_direction < 0 and close < float(c["vwap"])

        # Directional regimes require aligned 5m/15m trend. Sideways is a separate
        # compression-breakout setup; the middle of the range is never traded.
        bull_trend = (ctx.regime == BULL and bull_stack and ema21_rising and above_vwap
                      and float(c["adx"]) >= 22 and adx_rising
                      and float(c["plus_di"]) > float(c["minus_di"]) and rsi7 >= 55 and bull15)
        bear_trend = (ctx.regime == BEAR and bear_stack and ema21_falling and below_vwap
                      and float(c["adx"]) >= 22 and adx_rising
                      and float(c["minus_di"]) > float(c["plus_di"]) and rsi7 <= 45 and bear15)
        squeeze = bool(ctx.regime_detail.get("squeeze")) or bool(ctx.regime_detail.get("choppy"))
        bull_sideways = (ctx.regime == SIDEWAYS and squeeze and float(c["adx"]) >= 18 and adx_rising
                         and above_vwap and float(c["plus_di"]) > float(c["minus_di"])
                         and close > float(prior8["high"].max()) and bull15 and vol_ok)
        bear_sideways = (ctx.regime == SIDEWAYS and squeeze and float(c["adx"]) >= 18 and adx_rising
                         and below_vwap and float(c["minus_di"]) > float(c["plus_di"])
                         and close < float(prior8["low"].min()) and bear15 and vol_ok)

        if bull_trend:
            direction, trigger_kind = CE, ("breakout" if bull_break else "sweep" if bull_sweep else None)
        elif bear_trend:
            direction, trigger_kind = PE, ("breakout" if bear_break else "sweep" if bear_sweep else None)
        elif bull_sideways and rsi7 >= 52:
            direction, trigger_kind = CE, ("squeeze_breakout" if bull_break else None)
        elif bear_sideways and rsi7 <= 48:
            direction, trigger_kind = PE, ("squeeze_breakout" if bear_break else None)
        else:
            return None
        if trigger_kind is None:
            return None

        # Every mandatory gate above passed; the score only counts optional evidence, so the
        # threshold really filters (it is a quality bar, not a probability estimate).
        evidence = {
            "atr_expansion": atr_ratio >= 1.05,
            "volume": vol_ok,
            "room": self._room(liq, close, atr, direction) >= 1.0,
            "breadth": self._breadth_agrees(ctx, direction),
        }
        score = self.BASE_SCORE + sum(self.OPTIONAL_WEIGHTS[k] for k, ok in evidence.items() if ok)
        if score < float(self.tune.get("min_score", self.min_score)):
            return None
        stop = close - (1.5 * atr if direction == CE else -1.5 * atr)
        target = close + (2.0 * abs(close - stop) if direction == CE else -2.0 * abs(close - stop))
        # Stable per-day setup key: with reentry="setup" the same trigger in the same direction
        # cannot re-enter on every following bar (a timestamped key would allow that).
        key = f"ADMVE:{direction}:{trigger_kind}"
        passed = ",".join(k for k, ok in evidence.items() if ok) or "none"
        return Signal(direction, sl_price=stop, target=target, prem_sl_pct=self.prem_sl_pct,
                      setup_key=key,
                      note=f"ADMVE score {score}/100 ({passed}); regime {ctx.regime}; "
                           f"ATR expansion {atr_ratio:.2f}; liquidity {liq_score:.0f}; {trigger_kind}",
                      meta={"admve_score": score, "atr_ratio": atr_ratio, "liquidity_event": liq_event,
                            "liquidity_score": liq_score, "trigger": trigger_kind})

    @staticmethod
    def _room(liq: dict, close: float, atr: float, direction: str) -> float:
        """Distance in ATR to the nearest opposing liquidity level strictly beyond price
        (resistance above for CE, support below for PE); inf when none is known."""
        if direction == CE:
            levels = [z["price"] for z in liq.get("zones") or []
                      if z.get("kind") == "resistance" and z["price"] > close]
            return (min(levels) - close) / atr if levels else float("inf")
        levels = [z["price"] for z in liq.get("zones") or []
                  if z.get("kind") == "support" and z["price"] < close]
        return (close - max(levels)) / atr if levels else float("inf")

    @staticmethod
    def _breadth_agrees(ctx, direction: str) -> bool:
        breadth = ctx.aux.get("breadth")
        if breadth is None or not len(breadth.dropna()):
            return False
        latest = float(breadth.dropna().iloc[-1])
        return latest >= 1.2 if direction == CE else latest <= 0.8

    def exit_on_close(self, ctx, pos):
        c, d = ctx.last, pos["direction"]
        if d == CE and float(c["close"]) < float(c["ema21"]) and float(c["minus_di"]) > float(c["plus_di"]):
            return "ADMVE bullish momentum invalidated"
        if d == PE and float(c["close"]) > float(c["ema21"]) and float(c["plus_di"]) > float(c["minus_di"]):
            return "ADMVE bearish momentum invalidated"
        return None

    def trail_level(self, ctx, pos):
        c = ctx.last
        atr = float(c["atr"])
        if not np.isfinite(atr) or atr <= 0:
            return None
        return float(c["close"]) - (1.8 * atr if pos["direction"] == CE else -1.8 * atr)
