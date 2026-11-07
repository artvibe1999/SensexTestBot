"""Regressions for issues found in the code/security review."""
import asyncio
import json
import os
from datetime import date, datetime

import pytest

from sxpro.config import IST, Config
from sxpro.engine import Engine
from sxpro.market import build_context
from sxpro.store import Store

from .fakes import FakeKite, synthetic_candles


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


class LiveKite:
    """Minimal Kite double for LiveBroker: orders fill per a script, positions follow fills."""

    def __init__(self, held: int, fill_mode: str = "full", price: float = 100.0):
        self.held, self.fill_mode, self.price = held, fill_mode, price
        self.orders_: dict[str, dict] = {}
        self.n = 0
        self.ready = True

    def quote(self, keys):
        return {k: {"last_price": self.price,
                    "depth": {"buy": [{"price": self.price - 0.5, "quantity": 99}],
                              "sell": [{"price": self.price + 0.5, "quantity": 99}]}} for k in keys}

    def place_order(self, **kw):
        self.n += 1
        oid = f"o{self.n}"
        q = kw["quantity"]
        o = {"order_id": oid, "tradingsymbol": kw["tradingsymbol"], "transaction_type": kw["transaction_type"],
             "quantity": q, "status": "OPEN", "filled_quantity": 0, "pending_quantity": q,
             "average_price": 0.0, "order_type": kw["order_type"]}
        if kw["order_type"] == "SL":
            o["status"] = "TRIGGER PENDING"
        elif self.fill_mode == "full":
            o.update(status="COMPLETE", filled_quantity=q, pending_quantity=0, average_price=kw["price"])
        if o["status"] == "COMPLETE" and o["transaction_type"] == "SELL":
            self.held -= q
        self.orders_[oid] = o
        return oid

    def order_history(self, oid):
        return [dict(self.orders_[oid])]

    def cancel_order(self, oid):
        o = self.orders_[oid]
        if o["status"] not in ("COMPLETE", "CANCELLED", "REJECTED"):
            o["status"] = "CANCELLED"
            o["pending_quantity"] = 0

    def modify_order(self, oid, **kw):
        self.orders_[oid]["quantity"] = kw.get("quantity", self.orders_[oid]["quantity"])

    def positions(self):
        return {"net": [{"tradingsymbol": "SYM", "exchange": "BFO", "quantity": self.held}], "day": []}

    def orders(self):
        return list(self.orders_.values())

    # used by Engine but irrelevant here
    def expiries(self):
        return []

    def lot_size(self):
        return 20

    def funds(self):
        return {"net": 100000.0, "available": 100000.0, "utilised": 0.0}


def live_broker(cfg, kite):
    from sxpro.brokers import LiveBroker
    b = LiveBroker(kite, cfg)
    b._wait = lambda oid, timeout: b._state(oid)  # no sleeping in tests
    return b


def live_engine(cfg, kite):
    store = Store(cfg.db_path)
    eng = Engine(cfg, store, kite)
    eng.live = live_broker(cfg, kite)
    msgs: list[str] = []

    async def notify(t):
        msgs.append(t)
    eng.notify = notify
    return eng, store, msgs


def live_pos(**kw):
    base = {"id": "p1", "mode": "live", "strategy": "SENSEX_MOM_01", "direction": "CE", "symbol": "SYM",
            "token": 1, "strike": 77000, "expiry": "2026-11-12", "lot_size": 20, "tick": 0.05, "qty": 40,
            "initial_qty": 40, "entry_price": 100.0, "entry_time": "2026-11-04T10:00:00+05:30",
            "entry_candle": "2026-11-04 09:55:00+05:30", "underlying_entry": 77000.0, "sl_price": 76900.0,
            "stop_ref": 76900.0, "target": None, "book_fraction": 1.0, "booked": False, "prem_stop": 90.0,
            "prem_target": None, "trail_level": None, "trail_active": False, "sl_order_id": None,
            "time_exit": "15:15", "max_hold_min": 300, "meta": {}, "realized_gross": 0.0, "exit_value": 0.0,
            "exit_qty": 0, "exit_orders": 0, "last_ltp": 100.0, "exit_legs": []}
    base.update(kw)
    return base


def test_live_sell_never_exceeds_broker_quantity(cfg):
    from sxpro.brokers import FlatPosition
    k = LiveKite(held=20)
    b = live_broker(cfg, k)
    fill = b.sell("SYM", 40)  # bot thinks 40, Zerodha holds 20
    assert fill.qty == 20 and k.held == 0
    with pytest.raises(FlatPosition):
        b.sell("SYM", 20)
    assert all(o["quantity"] <= 20 for o in k.orders_.values())


def test_live_sell_keeps_own_sl_out_of_pending_count(cfg):
    k = LiveKite(held=40)
    b = live_broker(cfg, k)
    sl = b.place_stop("SYM", 40, 90)
    assert b.sell("SYM", 20, keep_order_ids=(sl,)).qty == 20   # partial booking with SL open
    with pytest.raises(RuntimeError):                          # SL already covers the rest
        b.sell("SYM", 20)


def test_cancel_stop_reports_partial_fill(cfg):
    k = LiveKite(held=40)
    b = live_broker(cfg, k)
    sl = b.place_stop("SYM", 40, 90)
    k.orders_[sl].update(status="OPEN", filled_quantity=20, pending_quantity=20, average_price=89.5)
    st = b.cancel_stop(sl)
    assert st.status == "CANCELLED" and st.filled == 20 and st.avg == 89.5


def test_close_with_partially_filled_sl_sells_only_the_rest(cfg):
    k = LiveKite(held=40)
    eng, store, _ = live_engine(cfg, k)
    pos = live_pos()
    pos["sl_order_id"] = eng.live.place_stop("SYM", 40, 90)
    k.orders_[pos["sl_order_id"]].update(status="OPEN", filled_quantity=20, pending_quantity=20, average_price=89.5)
    k.held = 20  # 20 already sold by the SL
    eng.positions = [pos]
    asyncio.run(eng.close(pos, "test exit"))
    t = store.trades("live")[0]
    assert t["qty"] == 40 and k.held == 0 and not eng.positions
    sells = [o for o in k.orders_.values() if o["transaction_type"] == "SELL" and o["order_type"] == "LIMIT"]
    assert sum(o["filled_quantity"] for o in sells) == 20


def test_gap_through_exchange_sl_triggers_bot_exit(cfg):
    k = LiveKite(held=40, price=80.0)
    eng, store, _ = live_engine(cfg, k)
    pos = live_pos()
    pos["sl_order_id"] = eng.live.place_stop("SYM", 40, 90)  # stays TRIGGER PENDING (limit skipped)
    eng.positions = [pos]
    base_quote = k.quote
    k.quote = lambda keys: {key: ({"last_price": 77500.0} if key == "BSE:SENSEX" else base_quote([key])[key])
                            for key in keys}
    asyncio.run(eng.monitor(datetime(2026, 11, 4, 11, 0, tzinfo=IST)))
    assert not eng.positions
    assert "exchange SL not filled" in store.trades("live")[0]["exit_reason"]


def test_missing_spot_does_not_trigger_underlying_stop(cfg):
    df = synthetic_candles(3)
    fake = FakeKite(df, date(2026, 11, 5))
    eng, _, _ = live_engine(cfg, fake)
    pos = live_pos(mode="paper", symbol=fake.options[30]["tradingsymbol"], prem_stop=0.05, sl_price=1.0)
    eng.positions = [pos]
    orig = fake.quote
    fake.quote = lambda keys: {k: v for k, v in orig(keys).items() if k != "BSE:SENSEX"}
    eng.last_spot = 0.0
    fake.now = df.index[-1]
    asyncio.run(eng.monitor(datetime(2026, 11, 4, 11, 0, tzinfo=IST)))
    assert eng.positions == [pos]


def test_zero_dte_opposing_candle_exit():
    from sxpro.strategies import STRATEGY_MAP
    df = synthetic_candles(3)
    part = df.iloc[:-40]
    ctx = build_context(part, part.index[-1].to_pydatetime(), {"open": 1, "high": 2, "low": 0.5, "close": 1.5})
    s = STRATEGY_MAP["SENSEX_0DTE_12"]
    c = ctx.last
    if not (c["bull"] or c["bear"]):
        pytest.skip("doji candle")
    pos = {"direction": "CE" if c["bear"] else "PE", "entry_candle": str(ctx.df.index[-2])}
    assert s.exit_on_close(ctx, pos) == "momentum stalled (opposing candle)"


def test_login_for_other_account_is_rejected(cfg, monkeypatch):
    from sxpro.kite_service import KiteService, TokenError
    monkeypatch.setenv("KITE_USER_ID", "AB1234")
    ks = KiteService(Config())
    ks.kite.set_access_token("ours")

    def fake_session(rt, api_secret):
        ks.kite.set_access_token("theirs")
        return {"access_token": "theirs", "user_id": "ZZ9999"}
    monkeypatch.setattr(ks.kite, "generate_session", fake_session)
    monkeypatch.setattr(ks.kite, "invalidate_access_token", lambda t: None)
    with pytest.raises(TokenError):
        ks.exchange_request_token("x" * 32)
    assert ks.kite.access_token == "ours" and not os.path.exists(Config().token_path)


def test_public_health_hides_internals(cfg):
    from aiohttp.test_utils import make_mocked_request
    from sxpro.web import build_app
    eng, _, _ = live_engine(cfg, FakeKite(synthetic_candles(3), date(2026, 11, 5)))
    app = build_app(eng)
    handler = next(r.handler for r in app.router.routes() if r.resource.canonical == "/health")

    async def call(remote):
        req = make_mocked_request("GET", "/health", app=app).clone(remote=remote)
        return json.loads((await handler(req)).text)
    assert asyncio.run(call("203.0.113.5")) == {"ok": True}
    assert "sheet" in asyncio.run(call("127.0.0.1"))
