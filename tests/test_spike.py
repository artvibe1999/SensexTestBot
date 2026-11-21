"""SENSEX_SPIKE_22 (ported from sensex-pro-bot): detector, arming rules, entry and exits."""
import asyncio
from datetime import date, datetime, time, timedelta

import pytest

from sxpro.config import IST, Config
from sxpro.engine import SPIKE_SID, Engine
from sxpro.spike import SpikeContract, SpikeDetector
from sxpro.store import Store
from sxpro.strategies import STRATEGY_MAP

from .fakes import FakeKite, synthetic_candles

DAY = date(2026, 11, 4)
C = SpikeContract(7, "SXCE", 80000.0, "CE", date(2026, 11, 6), 20, 0.05)
FAR = SpikeContract(8, "SXFAR", 80500.0, "CE", date(2026, 11, 6), 20, 0.05)


class Clock:
    def __init__(self, t):
        self.t = t
        self.mono = 0.0

    def now(self):
        return self.t

    def step(self, s):
        self.t += timedelta(seconds=s)
        self.mono += s


def tick(tok, bid, ask):
    return {"instrument_token": tok, "last_price": (bid + ask) / 2,
            "depth": {"buy": [{"price": bid, "quantity": 20}], "sell": [{"price": ask, "quantity": 20}]}}


def detector(clock, **kw):
    d = SpikeDetector(clock=clock.now, mono=lambda: clock.mono, **kw)
    d.configure_day(DAY, [C, FAR], 265)
    d.enabled = True
    got = []
    d.on_trigger = got.append
    return d, got


def feed_series(d, clock, tok, mids, spread=0.5, spot=80010.0):
    for m in mids:
        d.on_ticks([{"instrument_token": 265, "last_price": spot}, tick(tok, m - spread / 2, m + spread / 2)])
        clock.step(1)


def test_detects_spike_once_per_day():
    clock = Clock(datetime.combine(DAY, time(9, 15, 5), IST))
    d, got = detector(clock)
    feed_series(d, clock, 7, [200] * 15)                 # quiet, now past 09:15:20 with 10 s of history
    assert got == []
    feed_series(d, clock, 7, [204, 210, 217])            # +8.5% over the 10-s low
    assert len(got) == 1 and got[0].contract.symbol == "SXCE" and got[0].rise >= 0.08
    feed_series(d, clock, 7, [200] * 3 + [240])          # never twice in a day
    assert len(got) == 1 and d.fired_today


def test_no_trigger_before_window_wide_spread_or_far_strike():
    clock = Clock(datetime.combine(DAY, time(9, 15, 0), IST))
    d, got = detector(clock)
    feed_series(d, clock, 7, [200] * 11 + [230])          # spike at 09:15:11 < 09:15:20
    assert got == []
    clock2 = Clock(datetime.combine(DAY, time(9, 16), IST))
    d2, got2 = detector(clock2)
    feed_series(d2, clock2, 7, [200] * 12 + [230], spread=4.0)    # 1.7% spread > 0.8%
    feed_series(d2, clock2, 8, [200] * 12 + [230])                # strike 490 points from spot
    assert got2 == []
    clock3 = Clock(datetime.combine(DAY, time(9, 30, 1), IST))
    d3, got3 = detector(clock3)
    feed_series(d3, clock3, 7, [200] * 12 + [230])                # after 09:30
    assert got3 == []


@pytest.fixture
def eng(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "45000")
    candles = synthetic_candles(days=3, end=DAY)
    kite = FakeKite(candles, date(2026, 11, 6))
    e = Engine(Config(), Store(str(tmp_path / "sxpro.db")), kite)

    async def notify(t):
        e.sent.append(t)
    e.sent = []
    e.notify = notify
    return e


def _trigger(eng, ot="CE"):
    kite = eng.kite
    kite.now = datetime.combine(DAY, time(9, 15, 30), IST)
    eng.clock = lambda: kite.now
    spot = kite.spot()
    r = min((o for o in kite.options if o["instrument_type"] == ot), key=lambda o: abs(o["strike"] - spot))
    q = kite.quote([f"BFO:{r['tradingsymbol']}"])[f"BFO:{r['tradingsymbol']}"]
    from sxpro.spike import SpikeTrigger
    c = SpikeContract(r["instrument_token"], r["tradingsymbol"], r["strike"], ot, r["expiry"], 20, 0.05)
    bid, ask = q["depth"]["buy"][0]["price"], q["depth"]["sell"][0]["price"]
    return SpikeTrigger(c, kite.now, (bid + ask) / 2, (bid + ask) / 2 / 1.09, bid, ask, spot)


def _price(eng, factor_of_entry, pos):
    """Make every option quote trade at entry x factor from now on."""
    real = eng.kite.quote

    def q(keys):
        out = real(keys)
        px = pos["entry_price"] * factor_of_entry
        for k, v in out.items():
            if k.startswith("BFO:"):
                v["last_price"] = px
                v["depth"] = {"buy": [{"price": round(px - 0.05, 2), "quantity": 20}],
                              "sell": [{"price": round(px + 0.05, 2), "quantity": 20}]}
        return out
    eng.kite.quote = q


def _monitor_at(eng, dt):
    eng.kite.now = dt
    asyncio.run(eng.monitor(dt))


def test_off_at_start_and_enable_all_does_not_arm(eng):
    assert SPIKE_SID in eng.store.get("disabled")
    assert asyncio.run(eng.on_spike(_trigger(eng))) is None        # not armed
    from sxpro.telegram_bot import TelegramController
    ctl = TelegramController.__new__(TelegramController)
    ctl.engine = eng
    async def reply(update, text):
        eng.sent.append(text)
    ctl.reply = reply
    ctl._event = lambda *a: None
    asyncio.run(ctl._toggle(None, type("C", (), {"args": ["all"]})(), True))
    assert SPIKE_SID in eng.store.get("disabled")
    asyncio.run(ctl._toggle(None, type("C", (), {"args": ["SPIKE_22"]})(), True))
    assert SPIKE_SID not in eng.store.get("disabled") and eng.store.get(f"armed_{SPIKE_SID}")
    assert "armed for ONE PAPER trade" in eng.sent[-1]
    # a restart disarms it again
    Engine(eng.cfg, eng.store, eng.kite)
    assert SPIKE_SID in eng.store.get("disabled") and not eng.store.get(f"armed_{SPIKE_SID}")


def test_loss_stop_then_strategy_disables_itself(eng):
    eng.arm_spike(True)
    pos = asyncio.run(eng.on_spike(_trigger(eng, "PE")))
    assert pos is not None and pos["prem_stop"] == pytest.approx(pos["entry_price"] * 0.94, abs=0.06)
    assert not eng.store.get(f"armed_{SPIKE_SID}")                 # single trade: no second entry
    _price(eng, 0.9, pos)
    _monitor_at(eng, eng.kite.now + timedelta(seconds=20))
    t = eng.store.trades("paper")
    assert len(t) == 1 and t[0]["exit_reason"].startswith("premium stop") and t[0]["exit_price"] <= pos["prem_stop"]
    assert SPIKE_SID in eng.store.get("disabled") and "now disabled" in eng.sent[-1]
    assert asyncio.run(eng.on_spike(_trigger(eng))) is None


def test_flat_trade_closes_at_5_minutes(eng):
    eng.arm_spike(True)
    pos = asyncio.run(eng.on_spike(_trigger(eng)))
    _price(eng, 1.03, pos)                                          # in profit, but trail not armed
    _monitor_at(eng, eng.kite.now + timedelta(minutes=5, seconds=1))
    t = eng.store.trades("paper")
    assert len(t) == 1 and t[0]["exit_reason"].startswith("max holding")
    assert SPIKE_SID in eng.store.get("disabled")


def test_profit_trail_runs_past_0930_and_never_gives_back_profit(eng):
    eng.arm_spike(True)
    pos = asyncio.run(eng.on_spike(_trigger(eng)))
    entry = pos["entry_price"]
    t = eng.kite.now
    _price(eng, 1.30, pos)
    _monitor_at(eng, t + timedelta(minutes=2))                     # +30%: trail armed
    assert pos["prem_trail_stop"] == pytest.approx(max(1.30 * entry * 0.75, entry * 1.01), abs=0.02)
    _price(eng, 1.60, pos)
    _monitor_at(eng, datetime.combine(DAY, time(10, 45), IST))     # past 09:30 and past 5 minutes
    assert pos in eng.positions and pos["prem_trail_stop"] == pytest.approx(1.60 * entry * 0.75, abs=0.02)
    _price(eng, 1.15, pos)                                          # falls through the trail
    _monitor_at(eng, datetime.combine(DAY, time(11, 0), IST))
    tr = eng.store.trades("paper")
    assert len(tr) == 1 and tr[0]["exit_reason"].startswith("premium trail") and tr[0]["net_pnl"] > 0
    assert SPIKE_SID in eng.store.get("disabled")


def test_trail_floor_keeps_entry_plus_1pct(eng):
    eng.arm_spike(True)
    pos = asyncio.run(eng.on_spike(_trigger(eng)))
    entry = pos["entry_price"]
    _price(eng, 1.13, pos)
    _monitor_at(eng, eng.kite.now + timedelta(seconds=10))
    assert pos["prem_trail_stop"] == pytest.approx(entry * 1.01, abs=0.02)   # 1.13*0.75 < 1.01


def test_spike_trades_live_with_exchange_sl(eng):
    from sxpro.brokers import Fill
    eng.store.set("mode", "live")
    eng.arm_spike(True)                                                # armed for LIVE
    trig = _trigger(eng)
    orders = []
    eng.live.buy = lambda symbol, qty, tick=0.05: orders.append((symbol, qty)) or Fill(trig.ask, qty, "OID1")
    eng.live.place_stop = lambda sym, qty, trig_px, tick=0.05: orders.append(("SL", qty, trig_px)) or "SL1"
    pos = asyncio.run(eng.on_spike(trig))
    assert pos is not None and pos["mode"] == "live" and pos["sl_order_id"] == "SL1"
    assert orders[0][0] == trig.contract.symbol and orders[1][0] == "SL"
    assert orders[1][2] == pytest.approx(pos["entry_price"] * 0.94, abs=0.06)
    assert not eng.store.get(f"armed_{SPIKE_SID}")                     # single trade in live too
    assert STRATEGY_MAP[SPIKE_SID].in_window(None) is False


def test_prepare_spike_needs_arming_and_streams_near_atm(eng):
    started = []

    class StubFeed:
        running = False

        def start(self, token, tokens, cb):
            started.append(tokens)
            self.running = True

        def stop(self):
            self.running = False
    eng.spike_feed = StubFeed()
    now = datetime.combine(DAY, time(9, 13, 30), IST)
    eng.kite.now = now
    asyncio.run(eng.prepare_spike(now))
    assert not eng.spike.enabled and not started
    eng.arm_spike(True)
    asyncio.run(eng.prepare_spike(now))
    assert eng.spike.enabled and started and 265 in started[0]
    spot = eng.kite.spot()
    assert all(abs(c.strike - spot) <= 1500 for c in eng.spike._contracts.values())
    eng.store.set("paused", True)
    asyncio.run(eng.prepare_spike(now))
    assert not eng.spike.enabled


def test_mode_switch_disarms_and_arming_is_per_mode(eng):
    from types import SimpleNamespace
    from datetime import timedelta as td
    from sxpro.telegram_bot import TelegramController
    ctl = TelegramController.__new__(TelegramController)
    ctl.engine = eng
    ctl._live_confirm_until = None
    async def reply(update, text):
        eng.sent.append(text)
    ctl.reply = reply
    ctl._event = lambda *a: None
    eng.arm_spike(True)                                   # armed in PAPER
    assert eng.store.get(f"armed_{SPIKE_SID}") == "paper" and eng.spike_armed()
    ctl._live_confirm_until = datetime.now(IST) + td(minutes=1)
    asyncio.run(ctl.cmd_confirm_live(None, None))         # paper -> live
    assert eng.mode == "live" and not eng.spike_armed() and SPIKE_SID in eng.store.get("disabled")
    assert "disarmed by the mode switch" in eng.sent[-1]
    assert asyncio.run(eng.on_spike(_trigger(eng))) is None
    eng.arm_spike(True)                                   # re-armed for LIVE
    assert eng.store.get(f"armed_{SPIKE_SID}") == "live"
    asyncio.run(ctl.cmd_mode(None, SimpleNamespace(args=["paper"])))     # live -> paper
    assert not eng.spike_armed() and "disarmed" in eng.sent[-1]
    eng.arm_spike(True)
    asyncio.run(ctl.cmd_mode(None, SimpleNamespace(args=["paper"])))     # paper -> paper: no change
    assert eng.spike_armed()
    eng.store.set("mode", "live")                         # mode changed without Telegram: still not armed
    assert not eng.spike_armed()
