"""Black-Scholes greeks, implied volatility and the Strike Selection Engine."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

from .config import IST

EXPIRY_CLOSE = time(15, 30)


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(spot: float, strike: float, t: float, r: float, vol: float, is_call: bool) -> float:
    if t <= 0 or vol <= 0:
        return max(0.0, spot - strike) if is_call else max(0.0, strike - spot)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if is_call:
        return spot * _ncdf(d1) - strike * math.exp(-r * t) * _ncdf(d2)
    return strike * math.exp(-r * t) * _ncdf(-d2) - spot * _ncdf(-d1)


def bs_delta(spot: float, strike: float, t: float, r: float, vol: float, is_call: bool) -> float:
    """Absolute delta (0..1) for both calls and puts."""
    if t <= 0 or vol <= 0:
        itm = spot > strike if is_call else spot < strike
        return 1.0 if itm else 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    return _ncdf(d1) if is_call else 1.0 - _ncdf(d1)


def implied_vol(price: float, spot: float, strike: float, t: float, r: float, is_call: bool) -> Optional[float]:
    intrinsic = max(0.0, spot - strike) if is_call else max(0.0, strike - spot)
    if price <= intrinsic or t <= 0:
        return None
    lo, hi = 0.01, 5.0  # 500% cap: handles extreme-event IV spikes in SENSEX options
    for _ in range(80):
        mid = (lo + hi) / 2
        if bs_price(spot, strike, t, r, mid, is_call) > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-5:
            break
    return (lo + hi) / 2


def years_to_expiry(now: datetime, expiry: date) -> float:
    exp_dt = datetime.combine(expiry, EXPIRY_CLOSE, tzinfo=IST)
    secs = (exp_dt - now).total_seconds()
    return max(secs, 60.0) / (365.0 * 24 * 3600)


def option_delta(ltp: float, spot: float, strike: float, now: datetime, expiry: date, r: float,
                 is_call: bool) -> float:
    t = years_to_expiry(now, expiry)
    iv = implied_vol(ltp, spot, strike, t, r, is_call)
    if iv is None:
        # Premium below intrinsic (stale quote) or worthless: treat as deep ITM/OTM
        return bs_delta(spot, strike, t, r, 0.15, is_call)
    return bs_delta(spot, strike, t, r, iv, is_call)


# ------------------------------------------------------------------ expiry
def choose_expiry(expiries: list[date], today: date, rule: str, now_t: time) -> Optional[date]:
    """rule:
    - "weekly":     current weekly expiry; on expiry day (0DTE) roll to next week (framework sec. 5)
    - "0dte":       today's expiry only
    - "weekly_2pm": current weekly, but next weekly if after 14:00 on expiry day (strategy 3)
    - "next":       the weekly after the current one (strategy 51)
    """
    future = sorted(e for e in expiries if e >= today)
    if not future:
        return None
    nearest = future[0]
    nxt = future[1] if len(future) > 1 else None
    if rule == "0dte":
        return nearest if nearest == today else None
    if rule == "next":
        return nxt
    if nearest == today:
        if rule == "weekly_2pm" and now_t < time(14, 0):
            return nearest
        return nxt
    return nearest


@dataclass
class StrikeCandidate:
    tradingsymbol: str
    instrument_token: int
    strike: float
    option_type: str
    expiry: date
    lot_size: int
    tick_size: float
    ltp: float
    bid: float
    ask: float
    delta: float

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2
        return (self.ask - self.bid) / mid if mid > 0 and self.bid > 0 and self.ask > 0 else 1.0

    @property
    def entry_price(self) -> float:
        return self.ask if self.ask > 0 else self.ltp


def select_strike(candidates: list[StrikeCandidate], delta_min: float, delta_max: float, delta_target: float,
                  prem_min: float, prem_max: float, max_affordable: float, max_spread_pct: float
                  ) -> tuple[Optional[StrikeCandidate], str]:
    """Pick the candidate closest to `delta_target` that satisfies every filter.
    Returns (candidate, reason-if-none)."""
    if not candidates:
        return None, "no option quotes"
    reasons: dict[str, int] = {}
    ok: list[StrikeCandidate] = []
    for c in candidates:
        p = c.entry_price
        if p <= 0:
            reasons["no price"] = reasons.get("no price", 0) + 1
        elif not (delta_min <= c.delta <= delta_max):
            reasons["delta"] = reasons.get("delta", 0) + 1
        elif not (prem_min <= p <= prem_max):
            reasons["premium range"] = reasons.get("premium range", 0) + 1
        elif p > max_affordable:
            reasons["above max affordable premium"] = reasons.get("above max affordable premium", 0) + 1
        elif c.spread_pct > max_spread_pct:
            reasons["bid-ask spread"] = reasons.get("bid-ask spread", 0) + 1
        else:
            ok.append(c)
    if not ok:
        return None, "no strike passed filters (" + ", ".join(f"{k}:{v}" for k, v in reasons.items()) + ")"
    ok.sort(key=lambda c: (abs(c.delta - delta_target), c.spread_pct))
    return ok[0], ""
