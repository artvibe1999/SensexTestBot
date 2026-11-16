"""Causal SENSEX liquidity context built only from completed candles and current futures depth.

Liquidity levels are probabilistic areas, not observable stop orders. Futures depth is a
single snapshot and is deliberately treated as weak supporting evidence, never as a
standalone entry trigger. No order placement or risk decisions live in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class LiquidityZone:
    kind: str
    price: float
    score: float
    source: str


def _finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _depth_obi(snapshot: dict | None, levels: int = 5) -> float | None:
    """Top-of-book weighted imbalance in [-1, 1]; None for absent/invalid depth."""
    if not isinstance(snapshot, dict):
        return None
    try:
        depth = snapshot.get("depth") or {}
        bids, asks = depth.get("buy") or [], depth.get("sell") or []
        if not bids or not asks:
            return None
        bid_qty = ask_qty = 0.0
        for i, row in enumerate(bids[:levels]):
            q = float(row.get("quantity") or 0)
            if q > 0:
                bid_qty += q / (i + 1)
        for i, row in enumerate(asks[:levels]):
            q = float(row.get("quantity") or 0)
            if q > 0:
                ask_qty += q / (i + 1)
        total = bid_qty + ask_qty
        return (bid_qty - ask_qty) / total if total > 0 else None
    except (TypeError, ValueError, AttributeError):
        # Malformed depth must degrade to "no depth evidence", not break candle processing.
        return None


def analyze_liquidity(ctx, futures_quote: dict | None = None) -> dict:
    """Return zones, profile, sweep/acceptance events, and a cautious 0..100 score."""
    df = ctx.df
    if df is None or len(df) < 12:
        return {"available": False, "score": 0.0, "zones": [], "event": "insufficient_history",
                "obi": None, "support": None, "resistance": None}
    c = ctx.last
    price = float(c["close"])
    atr = float(c.get("atr", 0.0) or 0.0)
    if not _finite(price) or price <= 0 or not _finite(atr) or atr <= 0:
        return {"available": False, "score": 0.0, "zones": [], "event": "invalid_market_data",
                "obi": None, "support": None, "resistance": None}

    zones: list[LiquidityZone] = []
    # Prior-session and pivot levels are known before today's session.
    for name, value in (("PDH", ctx.pdh), ("PDL", ctx.pdl), ("P", ctx.pivots.get("P"))):
        if _finite(value):
            kind = "resistance" if float(value) >= price else "support"
            zones.append(LiquidityZone(kind, float(value), 72.0, name))
    # Confirmed local swing candidates: only candles ending before the current bar.
    hist = df.iloc[:-1].tail(60)
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    if len(hist) >= 5:
        highs = hist["high"].to_numpy(dtype=float)
        lows = hist["low"].to_numpy(dtype=float)
        for i in range(2, len(hist) - 2):
            if highs[i] >= max(highs[i - 2:i + 3]):
                value = float(highs[i])
                swing_highs.append(value)
                if abs(value - price) <= 3.0 * atr:
                    zones.append(LiquidityZone("resistance", value, 55.0, "confirmed_swing_high"))
            if lows[i] <= min(lows[i - 2:i + 3]):
                value = float(lows[i])
                swing_lows.append(value)
                if abs(value - price) <= 3.0 * atr:
                    zones.append(LiquidityZone("support", value, 55.0, "confirmed_swing_low"))
    # Equal-high / equal-low pools require at least two confirmed pivots in an ATR-scaled band.
    cluster_tol = max(0.10 * atr, 0.0005 * price)
    for values, kind, source in ((swing_highs, "resistance", "equal_high_cluster"),
                                 (swing_lows, "support", "equal_low_cluster")):
        for i, level in enumerate(values):
            matches = [v for v in values[:i] if abs(v - level) <= cluster_tol]
            if matches and abs(level - price) <= 3.0 * atr:
                zones.append(LiquidityZone(kind, float(np.mean(matches + [level])), 68.0, source))

    # Futures-volume proxy is carried on the SENSEX candle series by KiteService.
    session = ctx.today
    if len(session) >= 6:
        opening = session.iloc[:6]
        opening_high, opening_low = float(opening["high"].max()), float(opening["low"].min())
        if abs(opening_high - price) <= 3.0 * atr:
            zones.append(LiquidityZone("resistance", opening_high, 62.0, "30m_opening_range_high"))
        if abs(opening_low - price) <= 3.0 * atr:
            zones.append(LiquidityZone("support", opening_low, 62.0, "30m_opening_range_low"))
    vol = session["volume"].astype(float).clip(lower=0)
    total_vol = float(vol.sum())
    profile_poc = None
    profile_strength = 0.0
    if total_vol > 0:
        typical = (session["high"] + session["low"] + session["close"]) / 3.0
        bin_width = max(5.0, 0.10 * atr)
        bins = (typical / bin_width).round() * bin_width
        by_bin = vol.groupby(bins).sum()
        if not by_bin.empty:
            profile_poc = float(by_bin.idxmax())
            profile_strength = min(1.0, float(by_bin.max()) / max(total_vol, 1.0) * 8.0)
            zones.append(LiquidityZone("profile", profile_poc, 45.0 + 20.0 * profile_strength, "session_futures_volume_poc"))

    # Deduplicate near-identical levels, keeping the strongest evidence.
    zones.sort(key=lambda z: z.score, reverse=True)
    unique: list[LiquidityZone] = []
    tolerance = max(2.0 * float(c.get("tick_size", 1.0) or 1.0), 0.10 * atr)
    for zone in zones:
        if not any(z.kind == zone.kind and abs(z.price - zone.price) <= tolerance for z in unique):
            unique.append(zone)
    support = max((z for z in unique if z.kind == "support" and z.price <= price + 0.25 * atr),
                  key=lambda z: z.price, default=None)
    resistance = min((z for z in unique if z.kind == "resistance" and z.price >= price - 0.25 * atr),
                     key=lambda z: z.price, default=None)

    obi = _depth_obi(futures_quote)
    prior = df.iloc[-7:-1]
    prior_high = float(prior["high"].max()) if len(prior) else float("nan")
    prior_low = float(prior["low"].min()) if len(prior) else float("nan")
    buffer = max(0.05 * atr, 2.0 * float(c.get("tick_size", 1.0) or 1.0))
    event = "none"
    direction = 0
    # A sweep needs a completed close back through a pre-existing level; a wick alone is insufficient.
    if support and float(c["low"]) < support.price - buffer and price > support.price:
        event, direction = "bullish_sweep_reclaim", 1
    elif resistance and float(c["high"]) > resistance.price + buffer and price < resistance.price:
        event, direction = "bearish_sweep_reclaim", -1
    elif _finite(prior_high) and price > prior_high and float(c["close"]) > float(c["open"]):
        event, direction = "bullish_breakout", 1
    elif _finite(prior_low) and price < prior_low and float(c["close"]) < float(c["open"]):
        event, direction = "bearish_breakout", -1

    # Score is a confluence descriptor, not a probability or a validated trading edge.
    score = 35.0
    if support and abs(price - support.price) <= 0.75 * atr:
        score += 10.0
    if resistance and abs(resistance.price - price) <= 0.75 * atr:
        score += 10.0
    score += 15.0 * profile_strength
    # Futures depth (OBI) is deliberately kept out of the score: backtests have no depth
    # history, so a score that used it could not be reproduced. OBI only feeds ranking.
    if event != "none":
        score += 20.0
    score = float(min(100.0, max(0.0, score)))
    return {
        "available": True, "score": score, "zones": [
            {"kind": z.kind, "price": z.price, "strength": z.score, "source": z.source} for z in unique
        ],
        "event": event, "direction": direction, "obi": obi, "profile_poc": profile_poc,
        "support": support.price if support else None,
        "resistance": resistance.price if resistance else None,
        "futures_volume": total_vol, "buffer": buffer,
    }


def strategy_confluence(liquidity: dict | None, direction: str, category: str) -> tuple[int, str]:
    """0..2 ranking-only confluence. Never vetoes a strategy signal."""
    if not liquidity or not liquidity.get("available"):
        return 0, "liquidity unavailable"
    d = 1 if direction == "CE" else -1
    event = liquidity.get("event")
    event_d = int(liquidity.get("direction") or 0)
    points, notes = 0, []
    if category == "reversal" and event in ("bullish_sweep_reclaim", "bearish_sweep_reclaim") and event_d == d:
        points += 2
        notes.append("liquidity sweep/reclaim")
    elif category == "breakout" and event in ("bullish_breakout", "bearish_breakout") and event_d == d:
        points += 2
        notes.append("liquidity breakout")
    elif category == "trend" and event_d == d:
        points += 1
        notes.append("directional liquidity event")
    obi = liquidity.get("obi")
    if obi is not None and d * float(obi) >= 0.20 and points < 2:
        points += 1
        notes.append("futures depth confluence")
    return points, ", ".join(notes) or "no directional liquidity confluence"
