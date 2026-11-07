"""Zerodha charges & taxes per executed order.

Primary source is Kite's virtual contract note API (POST /charges/orders), which returns
Zerodha's own calculation (brokerage, STT, exchange txn charge, SEBI fee, stamp duty, GST)
for each order. If that call fails, an equivalent formula with Zerodha's published F&O
option rates is used.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Zerodha F&O options (BSE SENSEX) rates
BROKERAGE_PER_ORDER = 20.0
STT_SELL = 0.001          # 0.1% of sell premium
BSE_TXN = 0.000325        # 0.0325% of premium turnover (BSE index options)
SEBI = 10 / 1e7           # ₹10 per crore
STAMP_BUY = 0.00003       # 0.003% of buy premium
GST = 0.18                # on brokerage + exchange charge + SEBI fee


@dataclass
class OrderLeg:
    order_id: str
    tradingsymbol: str
    transaction_type: str   # BUY / SELL
    quantity: int
    average_price: float
    exchange: str = "BFO"
    product: str = "MIS"
    order_type: str = "LIMIT"
    variety: str = "regular"


def formula_charges(leg: OrderLeg) -> float:
    value = leg.quantity * leg.average_price
    if value <= 0:
        return 0.0
    brokerage = BROKERAGE_PER_ORDER  # options: flat ₹20 per executed order
    stt = STT_SELL * value if leg.transaction_type == "SELL" else 0.0
    txn = BSE_TXN * value
    sebi = SEBI * value
    stamp = STAMP_BUY * value if leg.transaction_type == "BUY" else 0.0
    gst = GST * (brokerage + txn + sebi)
    return round(brokerage + stt + txn + sebi + stamp + gst, 2)


def order_charges(kite_connect, legs: list[OrderLeg]) -> tuple[dict[str, float], str]:
    """Return ({order_id: total charges}, source) where source is 'zerodha' or 'estimate'."""
    if not legs:
        return {}, "zerodha"
    params = [{
        "order_id": l.order_id, "exchange": l.exchange, "tradingsymbol": l.tradingsymbol,
        "transaction_type": l.transaction_type, "variety": l.variety, "product": l.product,
        "order_type": l.order_type, "quantity": int(l.quantity), "average_price": float(l.average_price),
    } for l in legs]
    try:
        out: dict[str, float] = {}
        for i in range(0, len(params), 50):
            res = kite_connect.get_virtual_contract_note(params[i:i + 50])
            for p, r in zip(params[i:i + 50], res):
                out[p["order_id"]] = round(float(r["charges"]["total"]), 2)
        if len(out) == len(params):
            return out, "zerodha"
    except Exception as exc:
        log.warning("virtual contract note failed, using formula: %s", exc)
    return {l.order_id: formula_charges(l) for l in legs}, "estimate"
