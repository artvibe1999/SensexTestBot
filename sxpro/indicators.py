"""Technical indicators on OHLCV DataFrames (index = tz-aware candle start time).

All functions are pure and vectorised with pandas/numpy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    w /= w.sum()
    # np.convolve is ~10x faster than rolling().apply() with a Python callable
    arr = s.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    if len(arr) >= n:
        out[n - 1:] = np.convolve(arr, w[::-1], mode="full")[n - 1: len(arr)]
    return pd.Series(out, index=s.index, dtype=float)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame(
        {"adx": dx.ewm(alpha=1 / n, adjust=False).mean(), "plus_di": plus_di, "minus_di": minus_di}
    )


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower, "bb_width": (upper - lower) / mid})


def keltner(df: pd.DataFrame, n: int = 20, k: float = 1.5) -> pd.DataFrame:
    mid = ema(df["close"], n)
    a = atr(df, n)
    return pd.DataFrame({"kc_mid": mid, "kc_upper": mid + k * a, "kc_lower": mid - k * a})


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP that resets every trading day. Falls back to cumulative typical-price
    mean when the session has no volume."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    day = df.index.date
    vol = df["volume"].astype(float)
    pv = (tp * vol).groupby(day).cumsum()
    cv = vol.groupby(day).cumsum()
    vwap = pv / cv.replace(0, np.nan)
    fallback = tp.groupby(day).expanding().mean().reset_index(level=0, drop=True)
    return vwap.fillna(fallback)


def session_vwap_sd(df: pd.DataFrame, vwap: pd.Series) -> pd.Series:
    """Volume-weighted standard deviation of typical price around the session VWAP
    (unweighted when the session has no volume)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    day = df.index.date
    vol = df["volume"].astype(float)
    cv = vol.groupby(day).cumsum()
    m2 = (tp * tp * vol).groupby(day).cumsum() / cv.replace(0, np.nan)
    var = m2 - vwap * vwap
    fallback = tp.groupby(day).expanding().std(ddof=0).reset_index(level=0, drop=True)
    return np.sqrt(var.clip(lower=0)).fillna(fallback).fillna(0.0)


def ttm_momentum(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """TTM Squeeze momentum: linear-regression value (at the last bar) of
    close - mean(mean(highest high, lowest low), SMA) over `n` bars."""
    hh = df["high"].rolling(n, min_periods=n).max()
    ll = df["low"].rolling(n, min_periods=n).min()
    y = df["close"] - ((hh + ll) / 2 + sma(df["close"], n)) / 2
    x = np.arange(n, dtype=float)
    xm, xv = x.mean(), ((x - x.mean()) ** 2).sum()

    def endpoint(w: np.ndarray) -> float:
        if np.isnan(w).any():
            return np.nan
        b = ((x - xm) * (w - w.mean())).sum() / xv
        return w.mean() + b * (n - 1 - xm)
    return y.rolling(n, min_periods=n).apply(endpoint, raw=True)


def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.DataFrame:
    a = atr(df, n).to_numpy()
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy()
    close = df["close"].to_numpy()
    upper_basic, lower_basic = hl2 + mult * a, hl2 - mult * a
    upper, lower = upper_basic.copy(), lower_basic.copy()
    direction = np.ones(len(df), dtype=int)
    line = np.full(len(df), np.nan)
    for i in range(1, len(df)):
        upper[i] = upper_basic[i] if (upper_basic[i] < upper[i - 1] or close[i - 1] > upper[i - 1]) else upper[i - 1]
        lower[i] = lower_basic[i] if (lower_basic[i] > lower[i - 1] or close[i - 1] < lower[i - 1]) else lower[i - 1]
        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < lower[i] else 1
        else:
            direction[i] = 1 if close[i] > upper[i] else -1
        line[i] = lower[i] if direction[i] == 1 else upper[i]
    return pd.DataFrame({"st": line, "st_dir": direction}, index=df.index)


def psar(df: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    out = np.full(n, np.nan)
    if n < 2:
        return pd.Series(out, index=df.index)
    bull = high[1] >= high[0]
    sar = low[0] if bull else high[0]
    ep = high[0] if bull else low[0]
    af = step
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            sar = min(sar, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < sar:
                bull, sar, ep, af = False, ep, low[i], step
            elif high[i] > ep:
                ep, af = high[i], min(af + step, max_step)
        else:
            sar = max(sar, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > sar:
                bull, sar, ep, af = True, ep, high[i], step
            elif low[i] < ep:
                ep, af = low[i], min(af + step, max_step)
        out[i] = sar
    return pd.Series(out, index=df.index)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def stochastic(df: pd.DataFrame, n: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    ll = df["low"].rolling(n, min_periods=n).min()
    hh = df["high"].rolling(n, min_periods=n).max()
    raw = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    k = raw.rolling(k_smooth, min_periods=1).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": k.rolling(d_smooth, min_periods=1).mean()})


def pivots(high: float, low: float, close: float) -> dict[str, float]:
    p = (high + low + close) / 3
    return {
        "P": p,
        "R1": 2 * p - low, "S1": 2 * p - high,
        "R2": p + (high - low), "S2": p - (high - low),
        "R3": high + 2 * (p - low), "S3": low - 2 * (high - p),
    }


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add every indicator the strategies and regime engine need."""
    out = df.copy()
    c = out["close"]
    out["ema9"] = ema(c, 9)
    out["ema21"] = ema(c, 21)
    out["ema5"] = ema(c, 5)
    out["ema8"] = ema(c, 8)
    out["ema13"] = ema(c, 13)
    out["ema50"] = ema(c, 50)
    out["wma5"] = wma(c, 5)
    out["wma13"] = wma(c, 13)
    out["sma20"] = sma(c, 20)
    out["vwap"] = session_vwap(out)
    out["vwap_sd"] = session_vwap_sd(out, out["vwap"])
    out["atr"] = atr(out, 14)
    out["atr_sma10"] = sma(out["atr"], 10)
    out["rsi"] = rsi(c, 14)
    out = out.join(adx(out, 14))
    out = out.join(bollinger(c, 20, 2.0))
    out = out.join(keltner(out, 20, 1.5))
    out["squeeze_on"] = (out["bb_upper"] < out["kc_upper"]) & (out["bb_lower"] > out["kc_lower"])
    out["ttm_mom"] = ttm_momentum(out, 20)
    out = out.join(supertrend(out, 10, 3.0))
    out["psar"] = psar(out)
    out = out.join(macd(c))
    out = out.join(stochastic(out))
    vol = out["volume"].astype(float)
    out["vol_avg20"] = vol.shift(1).rolling(20, min_periods=5).mean()
    out["rvol"] = (vol / out["vol_avg20"].replace(0, np.nan)).fillna(0.0)
    rng = (out["high"] - out["low"]).replace(0, np.nan)
    out["range"] = out["high"] - out["low"]
    out["body"] = (out["close"] - out["open"]).abs()
    out["body_pct"] = (out["body"] / rng).fillna(0.0)
    out["upper_wick"] = out["high"] - out[["open", "close"]].max(axis=1)
    out["lower_wick"] = out[["open", "close"]].min(axis=1) - out["low"]
    out["upper_wick_pct"] = (out["upper_wick"] / rng).fillna(0.0)
    out["lower_wick_pct"] = (out["lower_wick"] / rng).fillna(0.0)
    out["bull"] = out["close"] > out["open"]
    out["bear"] = out["close"] < out["open"]
    return out
