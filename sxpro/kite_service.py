"""Zerodha Kite Connect wrapper: session/token handling, instruments, candles, quotes,
funds and orders. All methods are synchronous; the engine calls them in threads."""
from __future__ import annotations

import json
import logging
import os
import threading
import time as _time
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
from kiteconnect import KiteConnect
from kiteconnect import exceptions as kex

from .config import IST, Config

log = logging.getLogger(__name__)

INDEX_SYMBOL = "BSE:SENSEX"
INDEX_TOKEN_FALLBACK = 265
OPT_EXCHANGE = "BFO"


class TokenError(RuntimeError):
    pass


class _Throttle:
    def __init__(self, per_second: float):
        self.gap = 1.0 / per_second
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self) -> None:
        with self.lock:
            now = _time.monotonic()
            delay = self.last + self.gap - now
            if delay > 0:
                _time.sleep(delay)
            self.last = _time.monotonic()


class KiteService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.kite = KiteConnect(api_key=cfg.kite_api_key, timeout=15)
        self.ready = False
        self.user: dict = {}
        self._hist = _Throttle(2.5)
        self._quote = _Throttle(0.9)
        self._other = _Throttle(5)
        self._instr_day: Optional[date] = None
        self.options: list[dict] = []
        self.futures: list[dict] = []
        self.index_token = INDEX_TOKEN_FALLBACK

    # ------------------------------------------------------------ session
    def login_url(self) -> str:
        return self.kite.login_url()

    def _save_token(self, token: str) -> None:
        os.makedirs(self.cfg.data_dir, exist_ok=True)
        fd = os.open(self.cfg.token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"access_token": token, "saved_at": datetime.now(IST).isoformat()}, fh)
        try:
            os.chmod(self.cfg.token_path, 0o600)  # tighten a file created by an older version
        except OSError:
            pass

    def load_saved_token(self) -> bool:
        token = ""
        if os.path.exists(self.cfg.token_path):
            try:
                os.chmod(self.cfg.token_path, 0o600)
            except OSError:
                pass
            try:
                with open(self.cfg.token_path) as fh:
                    token = json.load(fh).get("access_token", "")
            except Exception:
                token = ""
        token = token or self.cfg.kite_access_token
        if not token:
            self.ready = False
            return False
        return self.activate(token)

    # The Zerodha account the bot trades. KITE_USER_ID pins it explicitly; otherwise the first
    # account that logs in is remembered (data/kite_user.json) and any other account is rejected,
    # so a stranger completing the public login link can never attach their account.
    @property
    def _pin_path(self) -> str:
        return os.path.join(self.cfg.data_dir, "kite_user.json")

    def expected_user(self) -> str:
        if self.cfg.kite_user_id.strip():
            return self.cfg.kite_user_id.strip().upper()
        try:
            with open(self._pin_path) as fh:
                return str(json.load(fh).get("user_id", "")).upper()
        except (OSError, ValueError):
            return ""

    def _pin_user(self, user_id: str) -> None:
        if not user_id or self.expected_user():
            return
        os.makedirs(self.cfg.data_dir, exist_ok=True)
        fd = os.open(self._pin_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"user_id": user_id.upper(), "pinned_at": datetime.now(IST).isoformat()}, fh)

    def activate(self, token: str) -> bool:
        self.kite.set_access_token(token)
        try:
            user = self.kite.profile()
        except Exception as exc:  # token expired / invalid
            log.info("access token invalid: %s", exc)
            self.ready = False
            return False
        expected = self.expected_user()
        if expected and str(user.get("user_id", "")).upper() != expected:
            log.error("access token belongs to %s, expected %s: not used", user.get("user_id"), expected)
            self.ready = False
            return False
        self.user = user
        self._pin_user(str(user.get("user_id", "")))
        self.ready = True
        return True

    def exchange_request_token(self, request_token: str) -> dict:
        previous = getattr(self.kite, "access_token", None)
        data = self.kite.generate_session(request_token, api_secret=self.cfg.kite_api_secret)
        token = data["access_token"]
        expected = self.expected_user()
        if expected and str(data.get("user_id", "")).upper() != expected:
            # Someone logged in with a different Zerodha account: never trade it.
            try:
                self.kite.invalidate_access_token(token)
            except Exception:
                pass
            self.kite.set_access_token(previous)  # generate_session swapped it in; restore ours
            raise TokenError(f"login was for user {data.get('user_id')}, expected {expected}; rejected")
        self._save_token(token)
        if not self.activate(token):
            raise TokenError("session generated but profile check failed")
        return self.user

    def _call(self, throttle: _Throttle, fn, *args, **kwargs):
        throttle.wait()
        try:
            return fn(*args, **kwargs)
        except kex.TokenException as exc:
            self.ready = False
            raise TokenError(str(exc)) from exc

    # ------------------------------------------------------------ instruments
    def refresh_instruments(self, force: bool = False) -> None:
        today = datetime.now(IST).date()
        if not force and self._instr_day == today and self.options:
            return
        rows = self._call(self._other, self.kite.instruments, OPT_EXCHANGE)
        sensex = [r for r in rows if r.get("name") == "SENSEX"]
        self.options = [r for r in sensex if r["instrument_type"] in ("CE", "PE") and r["expiry"] >= today]
        self.futures = sorted((r for r in sensex if r["instrument_type"] == "FUT" and r["expiry"] >= today),
                              key=lambda r: r["expiry"])
        try:
            q = self._call(self._quote, self.kite.quote, [INDEX_SYMBOL])
            self.index_token = int(q[INDEX_SYMBOL]["instrument_token"])
        except TokenError:
            raise
        except Exception:
            self.index_token = INDEX_TOKEN_FALLBACK
        self._instr_day = today
        log.info("instruments: %d SENSEX options, %d futures", len(self.options), len(self.futures))

    def expiries(self) -> list[date]:
        return sorted({r["expiry"] for r in self.options})

    def lot_size(self) -> int:
        if self.options:
            return int(self.options[0]["lot_size"])
        return 20

    def chain(self, expiry: date, spot: float, width: int = 10) -> list[dict]:
        rows = [r for r in self.options if r["expiry"] == expiry]
        strikes = sorted({r["strike"] for r in rows})
        if not strikes:
            return []
        atm = min(strikes, key=lambda s: abs(s - spot))
        i = strikes.index(atm)
        keep = set(strikes[max(0, i - width): i + width + 1])
        return [r for r in rows if r["strike"] in keep]

    def instrument_by_symbol(self, symbol: str) -> Optional[dict]:
        for r in self.options:
            if r["tradingsymbol"] == symbol:
                return r
        return None

    # ------------------------------------------------------------ market data
    def historical(self, token: int, start: datetime, end: datetime, interval: str) -> pd.DataFrame:
        rows = self._call(self._hist, self.kite.historical_data, token, start, end, interval)
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        if df["date"].dt.tz is None:
            df["date"] = df["date"].dt.tz_localize(IST)
        else:
            df["date"] = df["date"].dt.tz_convert(IST)
        return df.set_index("date")[["open", "high", "low", "close", "volume"]].astype(float)

    def index_candles(self, now: datetime, interval: str = "5minute", days: int = 8) -> pd.DataFrame:
        """SENSEX index OHLC with volume borrowed from the nearest SENSEX future
        (the index itself carries no volume). Only fully closed candles are returned."""
        start = now - timedelta(days=days)
        idx = self.historical(self.index_token, start, now, interval)
        if idx.empty:
            return idx
        idx["volume"] = 0.0
        if self.futures:
            try:
                fut = self.historical(int(self.futures[0]["instrument_token"]), start, now, interval)
                idx["volume"] = fut["volume"].reindex(idx.index).fillna(0.0)
            except TokenError:
                raise
            except Exception as exc:
                log.warning("futures volume unavailable: %s", exc)
        minutes = {"minute": 1, "3minute": 3, "5minute": 5, "15minute": 15}.get(interval, 5)
        closed = idx.index + pd.Timedelta(minutes=minutes) <= now
        return idx[closed]

    def daily_candles(self, now: datetime, days: int = 60) -> pd.DataFrame:
        return self.historical(self.index_token, now - timedelta(days=days), now, "day")

    def quote(self, keys: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for i in range(0, len(keys), 400):
            out.update(self._call(self._quote, self.kite.quote, keys[i:i + 400]))
        return out

    def spot(self) -> float:
        q = self.quote([INDEX_SYMBOL])
        return float(q[INDEX_SYMBOL]["last_price"])

    # ------------------------------------------------------------ funds
    def funds(self) -> dict:
        m = self._call(self._other, self.kite.margins, "equity")
        avail = m.get("available", {})
        cash = float(avail.get("live_balance", avail.get("cash", 0.0)))
        return {"net": float(m.get("net", 0.0)), "available": cash, "utilised": float(m.get("utilised", {}).get("debits", 0.0))}

    # ------------------------------------------------------------ orders
    def place_order(self, **kw) -> str:
        return self._call(self._other, self.kite.place_order, variety=self.kite.VARIETY_REGULAR,
                          exchange=OPT_EXCHANGE, product=self.cfg.product, validity=self.kite.VALIDITY_DAY,
                          tag="sxpro", **kw)

    def modify_order(self, order_id: str, **kw) -> str:
        return self._call(self._other, self.kite.modify_order, variety=self.kite.VARIETY_REGULAR,
                          order_id=order_id, **kw)

    def cancel_order(self, order_id: str) -> str:
        return self._call(self._other, self.kite.cancel_order, variety=self.kite.VARIETY_REGULAR,
                          order_id=order_id)

    def order_history(self, order_id: str) -> list[dict]:
        return self._call(self._other, self.kite.order_history, order_id)

    def positions(self) -> dict:
        return self._call(self._other, self.kite.positions)

    def orders(self) -> list[dict]:
        return self._call(self._other, self.kite.orders)
