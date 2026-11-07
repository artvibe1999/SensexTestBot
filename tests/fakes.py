"""Synthetic market + fake Kite for offline tests."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from sxpro.config import IST
from sxpro.kite_service import INDEX_SYMBOL
from sxpro.options import bs_price, years_to_expiry


def synthetic_candles(days: int = 6, seed: int = 1, start_price: float = 80000.0, drift: float = 0.0,
                      end: date = date(2026, 11, 4)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, price = [], start_price
    d = end - timedelta(days=days * 2)
    produced = 0
    while produced < days:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        produced += 1
        t = datetime.combine(d, time(9, 15), tzinfo=IST)
        price *= 1 + rng.normal(0, 0.003)
        for _ in range(75):
            o = price
            ret = rng.normal(drift, 0.0012)
            c = o * (1 + ret)
            h = max(o, c) * (1 + abs(rng.normal(0, 0.0005)))
            low = min(o, c) * (1 - abs(rng.normal(0, 0.0005)))
            vol = float(rng.integers(2000, 9000)) * (3 if abs(ret) > 0.002 else 1)
            rows.append((t, o, h, low, c, vol))
            price = c
            t += timedelta(minutes=5)
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"]).set_index("date")
    return df


class FakeKite:
    """Implements the subset of KiteService the engine uses (paper mode)."""

    def __init__(self, candles: pd.DataFrame, expiry: date):
        self.all = candles
        self.ready = True
        self.user = {"user_id": "TEST", "user_name": "Tester"}
        self.expiry = expiry
        self.now: datetime = candles.index[0]
        self.options = []
        for k in range(-30, 31):
            strike = round(candles["close"].iloc[-1] / 100) * 100 + 100 * k
            for ot in ("CE", "PE"):
                self.options.append({"tradingsymbol": f"SENSEX{expiry:%y%m%d}{int(strike)}{ot}",
                                     "instrument_token": 1000 + k * 2 + (ot == "PE"), "strike": float(strike),
                                     "instrument_type": ot, "expiry": expiry, "lot_size": 20, "tick_size": 0.05,
                                     "name": "SENSEX"})
        self.orders: list = []

    # session / instruments
    def load_saved_token(self):
        return True

    def refresh_instruments(self, force=False):
        return None

    def login_url(self):
        return "https://kite.example/login"

    def expiries(self):
        return [self.expiry, self.expiry + timedelta(days=7)]

    def lot_size(self):
        return 20

    def chain(self, expiry, spot, width=10):
        rows = [r for r in self.options if r["expiry"] == self.expiry]
        strikes = sorted({r["strike"] for r in rows})
        atm = min(strikes, key=lambda s: abs(s - spot))
        i = strikes.index(atm)
        keep = set(strikes[max(0, i - width): i + width + 1])
        return [r for r in rows if r["strike"] in keep]

    # data
    def _spot(self) -> float:
        part = self.all[self.all.index <= self.now]
        return float(part["close"].iloc[-1])

    def index_candles(self, now, interval="5minute", days=8):
        mins = 3 if interval == "3minute" else 5
        df = self.all
        if mins == 3:
            df = df.resample("3min").agg({"open": "first", "high": "max", "low": "min", "close": "last",
                                          "volume": "sum"}).dropna()
        return df[df.index + pd.Timedelta(minutes=mins) <= now].copy()

    def daily_candles(self, now, days=60):
        d = self.all.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last",
                                         "volume": "sum"}).dropna()
        return d

    def quote(self, keys):
        spot = self._spot()
        out = {}
        for k in keys:
            if k == INDEX_SYMBOL:
                out[k] = {"last_price": spot, "instrument_token": 265}
                continue
            sym = k.split(":", 1)[1]
            r = next(o for o in self.options if o["tradingsymbol"] == sym)
            t = years_to_expiry(self.now, self.expiry)
            px = max(0.05, bs_price(spot, r["strike"], t, 0.065, 0.14, r["instrument_type"] == "CE"))
            spread = max(0.05, round(px * 0.002, 2))
            out[k] = {"last_price": round(px, 2),
                      "depth": {"buy": [{"price": round(px - spread, 2), "quantity": 100}],
                                "sell": [{"price": round(px + spread, 2), "quantity": 100}]}}
        return out

    def spot(self):
        return self._spot()

    def funds(self):
        return {"net": 500000.0, "available": 450000.0, "utilised": 0.0}
