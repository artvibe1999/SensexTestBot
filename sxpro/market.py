"""Market context shared by the regime engine and all strategies."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional

import numpy as np
import pandas as pd

from . import indicators as ind

# Regime labels
BULL, BEAR, SIDEWAYS, NEUTRAL = "BULLISH", "BEARISH", "SIDEWAYS", "NEUTRAL"


@dataclass
class MarketContext:
    df: pd.DataFrame                    # enriched closed 5-min candles (several days)
    now: datetime
    prev_day: dict                      # open/high/low/close of previous session
    daily_adx: float = float("nan")
    nearest_expiry: Optional[date] = None
    df15: Optional[pd.DataFrame] = None
    regime: str = NEUTRAL
    regime_detail: dict = field(default_factory=dict)
    # Optional extra feeds, filled only when an enabled strategy declares `needs`:
    # vix (Series, today's 5m India VIX), nifty (DataFrame, today's 5m NIFTY 50 OHLC),
    # breadth (Series, today's advance/decline ratio of the SENSEX heavyweights per 5m
    # candle), oi ({"expiry", "CE": {strike: oi}, "PE": {...}}), first_min (Series, the
    # 09:15 1-minute candle), daily (DataFrame of recent daily candles before today).
    aux: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.today_date = self.df.index[-1].date()
        self.today = self.df[self.df.index.date == self.today_date]
        self.pivots = ind.pivots(self.prev_day["high"], self.prev_day["low"], self.prev_day["close"])

    # -------- convenience accessors --------
    @property
    def last(self) -> pd.Series:
        return self.df.iloc[-1]

    def c(self, back: int = 0) -> pd.Series:
        """Candle `back` bars ago (0 = last closed candle)."""
        return self.df.iloc[-1 - back]

    @property
    def n_today(self) -> int:
        return len(self.today)

    @property
    def last_time(self) -> time:
        return self.df.index[-1].time()

    @property
    def close_time(self) -> time:
        """Time at which the last candle closed (start + 5 min)."""
        ts = self.df.index[-1] + pd.Timedelta(minutes=5)
        return ts.time()

    @property
    def is_expiry_day(self) -> bool:
        return self.nearest_expiry is not None and self.nearest_expiry == self.today_date

    @property
    def pdh(self) -> float:
        return float(self.prev_day["high"])

    @property
    def pdl(self) -> float:
        return float(self.prev_day["low"])

    @property
    def pdc(self) -> float:
        return float(self.prev_day["close"])

    def orb(self, minutes: int = 30) -> tuple[float, float] | None:
        n = minutes // 5
        if self.n_today < n:
            return None
        first = self.today.iloc[:n]
        return float(first["high"].max()), float(first["low"].min())

    def range_until(self, end: time) -> tuple[float, float] | None:
        part = self.today[self.today.index.time < end]
        if part.empty:
            return None
        return float(part["high"].max()), float(part["low"].min())

    def day_high_low(self, exclude_last: int = 0) -> tuple[float, float]:
        part = self.today.iloc[: len(self.today) - exclude_last] if exclude_last else self.today
        if part.empty:
            part = self.today
        return float(part["high"].max()), float(part["low"].min())

    def vwap_slope_bps(self, lookback: int = 3) -> float:
        """VWAP change over `lookback` candles in basis points of price."""
        if self.n_today <= lookback:
            return 0.0
        v = self.today["vwap"]
        return float((v.iloc[-1] - v.iloc[-1 - lookback]) / v.iloc[-1] * 10_000)

    def vwap_crosses(self, lookback: int = 12) -> int:
        part = self.today.tail(lookback)
        side = np.sign(part["close"] - part["vwap"])
        return int((side.diff().abs() > 0).sum())

    def levels(self) -> dict[str, float]:
        lv = dict(self.pivots)
        lv["PDH"], lv["PDL"], lv["PDC"] = self.pdh, self.pdl, self.pdc
        return lv

    def swing_high(self, lookback: int, skip: int = 1) -> float:
        part = self.df.iloc[-lookback - skip: -skip] if skip else self.df.iloc[-lookback:]
        return float(part["high"].max())

    def swing_low(self, lookback: int, skip: int = 1) -> float:
        part = self.df.iloc[-lookback - skip: -skip] if skip else self.df.iloc[-lookback:]
        return float(part["low"].min())


# ---------------------------------------------------------------- patterns
def is_bull_engulfing(cur: pd.Series, prev: pd.Series) -> bool:
    return bool(cur["bull"] and cur["close"] >= max(prev["open"], prev["close"])
                and cur["open"] <= min(prev["open"], prev["close"]) and cur["body"] > prev["body"])


def is_bear_engulfing(cur: pd.Series, prev: pd.Series) -> bool:
    return bool(cur["bear"] and cur["close"] <= min(prev["open"], prev["close"])
                and cur["open"] >= max(prev["open"], prev["close"]) and cur["body"] > prev["body"])


def is_bull_pin(c: pd.Series, wick_pct: float = 0.5) -> bool:
    """Hammer / bullish pin bar: long lower wick, close in upper part."""
    return bool(c["range"] > 0 and c["lower_wick_pct"] >= wick_pct and c["lower_wick"] >= 2 * c["body"]
                and c["upper_wick_pct"] <= 0.3)


def is_bear_pin(c: pd.Series, wick_pct: float = 0.5) -> bool:
    """Shooting star / bearish pin bar."""
    return bool(c["range"] > 0 and c["upper_wick_pct"] >= wick_pct and c["upper_wick"] >= 2 * c["body"]
                and c["lower_wick_pct"] <= 0.3)


def is_doji(c: pd.Series, max_body_pct: float = 0.1) -> bool:
    return bool(c["range"] > 0 and c["body_pct"] <= max_body_pct)


def is_inside(cur: pd.Series, mother: pd.Series) -> bool:
    return bool(cur["high"] < mother["high"] and cur["low"] > mother["low"])


# ---------------------------------------------------------------- regime
def resample_15(df: pd.DataFrame) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = df[["open", "high", "low", "close", "volume"]].resample(
        "15min", origin="start_day", offset="15min"
    ).agg(agg).dropna()
    return out


def classify_regime(ctx: MarketContext, vwap_slope_bps_min: float = 2.0) -> tuple[str, dict]:
    """Market Regime Identification Engine (framework section 2) on 5m, confirmed on 15m."""
    if ctx.n_today < 3:
        return NEUTRAL, {"reason": "warming up"}
    d = ctx.df
    last = d.iloc[-1]
    slope = ctx.vwap_slope_bps(3)
    ema9_up = d["ema9"].iloc[-1] > d["ema9"].iloc[-3]
    ema21_up = d["ema21"].iloc[-1] > d["ema21"].iloc[-3]
    ema9_dn = d["ema9"].iloc[-1] < d["ema9"].iloc[-3]
    ema21_dn = d["ema21"].iloc[-1] < d["ema21"].iloc[-3]
    recent = d.tail(6)
    rvol_bull = float(recent.loc[recent["bull"], "rvol"].max()) if recent["bull"].any() else 0.0
    rvol_bear = float(recent.loc[recent["bear"], "rvol"].max()) if recent["bear"].any() else 0.0
    has_volume = float(d["volume"].tail(20).sum()) > 0

    bull5 = (last["close"] > last["vwap"] and slope > vwap_slope_bps_min
             and last["ema9"] > last["ema21"] and ema9_up and ema21_up
             and last["adx"] > 25 and last["plus_di"] > last["minus_di"]
             and (rvol_bull > 1.5 or not has_volume))
    bear5 = (last["close"] < last["vwap"] and slope < -vwap_slope_bps_min
             and last["ema9"] < last["ema21"] and ema9_dn and ema21_dn
             and last["adx"] > 25 and last["minus_di"] > last["plus_di"]
             and (rvol_bear > 1.5 or not has_volume))

    bull15 = bear15 = True
    if ctx.df15 is not None and len(ctx.df15) >= 30:
        l15 = ctx.df15.iloc[-1]
        bull15 = bool(l15["ema9"] > l15["ema21"] and l15["plus_di"] > l15["minus_di"])
        bear15 = bool(l15["ema9"] < l15["ema21"] and l15["minus_di"] > l15["plus_di"])

    bw = d["bb_width"]
    squeeze = bool(bw.iloc[-1] <= bw.tail(50).quantile(0.25)) if bw.notna().sum() > 20 else False
    choppy = ctx.vwap_crosses(12) >= 3 and abs(slope) <= vwap_slope_bps_min

    detail = {
        "adx": round(float(last["adx"]), 1), "+di": round(float(last["plus_di"]), 1),
        "-di": round(float(last["minus_di"]), 1), "vwap_slope_bps": round(slope, 2),
        "squeeze": squeeze, "choppy": choppy, "bull15": bull15, "bear15": bear15,
    }
    if bull5 and bull15:
        return BULL, detail
    if bear5 and bear15:
        return BEAR, detail
    if last["adx"] < 20 and (squeeze or choppy):
        return SIDEWAYS, detail
    return NEUTRAL, detail


def build_context(df5: pd.DataFrame, now: datetime, prev_day: dict, daily_adx: float = float("nan"),
                  nearest_expiry: Optional[date] = None, aux: Optional[dict] = None) -> MarketContext:
    enriched = ind.enrich(df5)
    df15 = ind.enrich(resample_15(df5)) if len(df5) >= 45 else None
    ctx = MarketContext(df=enriched, now=now, prev_day=prev_day, daily_adx=daily_adx,
                        nearest_expiry=nearest_expiry, df15=df15, aux=aux or {})
    ctx.regime, ctx.regime_detail = classify_regime(ctx)
    return ctx
