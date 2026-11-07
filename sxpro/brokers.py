"""Order execution. PaperBroker simulates fills on live Zerodha quotes; LiveBroker
places real orders through Kite (marketable LIMIT orders + exchange SL order).

Live safety rules:
* never sell more than Zerodha says is held (net qty minus other pending sell orders),
  so a late fill / failed cancel can never leave the account short an option;
* every cancel waits for the order's terminal state and reports any partial fill.
"""
from __future__ import annotations

import logging
import math
import time as _time
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .config import Config
from .kite_service import OPT_EXCHANGE, KiteService

log = logging.getLogger(__name__)

TERMINAL = ("COMPLETE", "REJECTED", "CANCELLED")
PENDING = ("OPEN", "TRIGGER PENDING", "OPEN PENDING", "VALIDATION PENDING", "PUT ORDER REQ RECEIVED",
           "MODIFY PENDING", "MODIFY VALIDATION PENDING", "CANCEL PENDING", "AMO REQ RECEIVED")


def round_tick(price: float, tick: float = 0.05, up: bool = True) -> float:
    n = price / tick
    n = math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)
    return round(max(n, 1) * tick, 2)


@dataclass
class Fill:
    price: float
    qty: int
    order_id: str = ""
    uncertain: bool = False      # order still working at the exchange after cancel attempt


@dataclass
class OrderState:
    status: str = "NONE"
    filled: int = 0
    avg: float = 0.0
    order_id: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL or self.status == "NONE"


class FlatPosition(RuntimeError):
    """Zerodha shows nothing left to sell for this symbol."""


def _best(quote: dict, side: str) -> float:
    depth = quote.get("depth") or {}
    book = depth.get("sell" if side == "buy" else "buy") or []
    for lvl in book:
        if lvl.get("price", 0) > 0 and lvl.get("quantity", 0) > 0:
            return float(lvl["price"])
    return float(quote.get("last_price", 0.0))


class PaperBroker:
    mode = "paper"

    def __init__(self, kite: KiteService):
        self.kite = kite

    def _q(self, symbol: str) -> dict:
        key = f"{OPT_EXCHANGE}:{symbol}"
        return self.kite.quote([key]).get(key, {})

    def buy(self, symbol: str, qty: int, tick: float = 0.05) -> Fill:
        price = _best(self._q(symbol), "buy")
        if price <= 0:
            raise RuntimeError(f"no ask price for {symbol}")
        return Fill(round(price, 2), qty, "PAPER")

    def sell(self, symbol: str, qty: int, tick: float = 0.05, floor_price: float | None = None,
             keep_order_ids: Iterable[str] = ()) -> Fill:
        price = _best(self._q(symbol), "sell")
        if floor_price is not None and floor_price > 0:
            # stop triggered: fill at the worse of stop and bid (gap-through realism)
            price = min(price, floor_price) if price > 0 else floor_price
        if price <= 0:
            raise RuntimeError(f"no bid price for {symbol}")
        return Fill(round(price, 2), qty, "PAPER")

    def place_stop(self, symbol: str, qty: int, trigger: float, tick: float = 0.05) -> Optional[str]:
        return None

    def modify_stop(self, order_id: Optional[str], qty: int, trigger: float, tick: float = 0.05) -> Optional[str]:
        return order_id

    def cancel_stop(self, order_id: Optional[str]) -> OrderState:
        return OrderState()

    def stop_filled(self, order_id: Optional[str]) -> Optional[Fill]:
        return None

    def broker_qty(self, symbol: str) -> Optional[int]:
        return None


class LiveBroker(PaperBroker):
    mode = "live"

    def __init__(self, kite: KiteService, cfg: Config):
        super().__init__(kite)
        self.cfg = cfg

    # ------------------------------------------------------------ helpers
    def _state(self, order_id: str) -> OrderState:
        hist = self.kite.order_history(order_id)
        if not hist:
            return OrderState(order_id=order_id)
        last = hist[-1]
        return OrderState(last["status"], int(last.get("filled_quantity") or 0),
                          float(last.get("average_price") or 0.0), order_id, last)

    def _wait(self, order_id: str, timeout: float) -> OrderState:
        deadline = _time.monotonic() + timeout
        while True:
            st = self._state(order_id)
            if st.status in TERMINAL or _time.monotonic() >= deadline:
                return st
            _time.sleep(0.6)

    def _cancel_and_settle(self, order_id: str) -> OrderState:
        try:
            self.kite.cancel_order(order_id)
        except Exception as exc:  # already complete / cancelled, or a transient API error
            log.info("cancel %s: %s", order_id, exc)
        return self._wait(order_id, 8)

    def broker_qty(self, symbol: str) -> Optional[int]:
        net = self.kite.positions().get("net", [])
        return sum(int(p.get("quantity") or 0) for p in net
                   if p.get("tradingsymbol") == symbol and p.get("exchange") == OPT_EXCHANGE)

    def _sellable(self, symbol: str, keep_order_ids: Iterable[str]) -> int:
        held = self.broker_qty(symbol) or 0
        keep = set(keep_order_ids)
        pending = sum(int(o.get("pending_quantity") or 0) for o in self.kite.orders()
                      if o.get("tradingsymbol") == symbol and o.get("transaction_type") == "SELL"
                      and o.get("status") in PENDING and o.get("order_id") not in keep)
        return max(0, held - pending)

    # ------------------------------------------------------------ orders
    def buy(self, symbol: str, qty: int, tick: float = 0.05) -> Fill:
        ask = _best(self._q(symbol), "buy")
        if ask <= 0:
            raise RuntimeError(f"no ask price for {symbol}")
        limit = round_tick(ask * (1 + self.cfg.limit_buffer_pct), tick, up=True)
        oid = self.kite.place_order(tradingsymbol=symbol, transaction_type="BUY", quantity=qty,
                                    order_type="LIMIT", price=limit)
        st = self._wait(oid, self.cfg.order_fill_timeout_s)
        if st.status == "REJECTED":
            raise RuntimeError(f"entry rejected: {st.raw.get('status_message')}")
        if st.status not in TERMINAL:
            st = self._cancel_and_settle(oid)
        return Fill(st.avg or limit, st.filled, oid, uncertain=st.status not in TERMINAL)

    def sell(self, symbol: str, qty: int, tick: float = 0.05, floor_price: float | None = None,
             keep_order_ids: Iterable[str] = ()) -> Fill:
        remaining, value, oid = qty, 0.0, ""
        keep = tuple(keep_order_ids)
        for attempt in range(5):
            can_sell = min(remaining, self._sellable(symbol, keep))
            if can_sell <= 0:
                break
            q = self._q(symbol)
            bid = _best(q, "sell")
            ref = bid if bid > 0 else float(q.get("last_price", 0.0))
            factor = self.cfg.limit_buffer_pct * (attempt + 1) * (3 if attempt == 4 else 1)
            limit = round_tick(max(tick, ref * (1 - factor)), tick, up=False)
            oid = self.kite.place_order(tradingsymbol=symbol, transaction_type="SELL", quantity=can_sell,
                                        order_type="LIMIT", price=limit)
            st = self._wait(oid, self.cfg.order_fill_timeout_s)
            if st.status == "REJECTED":
                raise RuntimeError(f"exit rejected: {st.raw.get('status_message')}")
            if st.status not in TERMINAL:
                st = self._cancel_and_settle(oid)
            value += st.filled * (st.avg or limit)
            remaining -= st.filled
            if st.status not in TERMINAL:
                # Order still working: stop here; _sellable() keeps the next attempt from double-selling.
                log.warning("exit order %s still %s after cancel", oid, st.status)
                break
            if remaining <= 0:
                break
        sold = qty - remaining
        if sold <= 0:
            if (self.broker_qty(symbol) or 0) <= 0:
                raise FlatPosition(f"Zerodha shows no {symbol} left to sell")
            raise RuntimeError(f"exit not filled for {symbol}")
        return Fill(round(value / sold, 2), sold, oid)

    def place_stop(self, symbol: str, qty: int, trigger: float, tick: float = 0.05) -> Optional[str]:
        trig = round_tick(trigger, tick, up=False)
        price = round_tick(max(tick, trig * 0.95), tick, up=False)
        return self.kite.place_order(tradingsymbol=symbol, transaction_type="SELL", quantity=qty,
                                     order_type="SL", trigger_price=trig, price=price)

    def modify_stop(self, order_id: Optional[str], qty: int, trigger: float, tick: float = 0.05) -> Optional[str]:
        if not order_id:
            return None
        trig = round_tick(trigger, tick, up=False)
        price = round_tick(max(tick, trig * 0.95), tick, up=False)
        self.kite.modify_order(order_id, quantity=qty, trigger_price=trig, price=price, order_type="SL")
        return order_id

    def cancel_stop(self, order_id: Optional[str]) -> OrderState:
        """Cancel the exchange SL order and return its terminal state (incl. any partial fill)."""
        if not order_id:
            return OrderState()
        st = self._state(order_id)
        if st.status in TERMINAL:
            return st
        return self._cancel_and_settle(order_id)

    def stop_filled(self, order_id: Optional[str]) -> Optional[Fill]:
        if not order_id:
            return None
        st = self._state(order_id)
        if st.status == "COMPLETE":
            return Fill(st.avg, st.filled, order_id)
        return None
