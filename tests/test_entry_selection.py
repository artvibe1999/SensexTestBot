"""Entry selection: every enabled strategy is checked, each signal gets the full pre-trade
check (strike, lots, margin, loss cap), the best plan that passes is placed, and strategies
enabled later rank after ADMVE and the verified set."""
import asyncio
from datetime import time, timedelta

import pytest

from sxpro.config import Config
from sxpro.engine import Engine
from sxpro.store import Store
from sxpro.strategies import ALL_STRATEGIES, STRATEGY_MAP
from sxpro.strategies.base import CE, PE, Signal, Strategy
from sxpro.strategies.tuning import DEFAULT_DENY_FLAG

from .fakes import FakeKite, synthetic_candles
from .test_bot import _run_day

VERIFIED = ["SENSEX_NOISE_61", "SENSEX_ORB60_74", "SENSEX_INSIDE_71", "SENSEX_3DAY_75",
            "SENSEX_LATEMOM_63", "SENSEX_HLBRK_66"]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


class _Forced(Strategy):
    start, end = time(10, 0), time(10, 5)
    prem_min, prem_max = 1, 5000
    delta_min, delta_max = 0.3, 0.7
    direction = CE

    def entry(self, ctx):
        c = float(ctx.last["close"])
        d = 1 if self.direction == CE else -1
        return Signal(self.direction, sl_price=c - d * 400, note="forced")


class Impossible(_Forced):
    sid, name = "TEST_IMPOSSIBLE", "no strike can pass"
    prem_min, prem_max = 1e6, 2e6


class Call(_Forced):
    sid, name = "TEST_CALL", "call"


class Put(_Forced):
    sid, name = "TEST_PUT", "put"
    direction = PE


def _engine(cfg, monkeypatch, strategies, drift=0.0004, seed=7):
    df = synthetic_candles(6, seed=seed, drift=drift)
    day = sorted(set(df.index.date))[-1]
    fake = FakeKite(df, expiry=day + timedelta(days=1))
    store = Store(cfg.db_path)
    engine = Engine(cfg, store, fake)
    msgs: list[str] = []

    async def notify(text):
        msgs.append(text)
    engine.notify = notify
    import sxpro.engine as eng
    monkeypatch.setattr(eng, "STRATEGY_MAP", {**eng.STRATEGY_MAP, **{s.sid: s for s in strategies}})
    monkeypatch.setattr(Engine, "enabled_strategies", lambda self: sorted(strategies, key=self.strategy_rank))
    store.set("lots_paper", 2)
    return engine, fake, day, store, msgs


def test_added_strategies_rank_after_admve_and_verified_six(cfg):
    store = Store(cfg.db_path)
    keep = set(VERIFIED) | {"SENSEX_VWAP_03", "SENSEX_VBO_62", "SENSEX_TRAP_02"}
    store.set("disabled", [s.sid for s in ALL_STRATEGIES if s.sid not in keep])
    store.set(DEFAULT_DENY_FLAG, True)   # extras switched on with /enable after the default-deny clean-up
    engine = Engine(cfg, store, FakeKite(synthetic_candles(2), synthetic_candles(2).index[-1].date()))
    order = [s.sid for s in engine.enabled_strategies()]
    assert order[:7] == ["SENSEX_ADMVE_80"] + VERIFIED
    assert set(order[7:]) == {"SENSEX_VWAP_03", "SENSEX_VBO_62", "SENSEX_TRAP_02"}
    assert all(engine.strategy_rank(STRATEGY_MAP[s])[0] == 2 for s in order[7:])


def test_failed_check_falls_through_to_next_strategy(cfg, monkeypatch):
    imp, call = Impossible(), Call()
    monkeypatch.setattr("sxpro.engine.VERIFIED_INDEX", {imp.sid: 1, call.sid: 2})
    engine, fake, day, store, msgs = _engine(cfg, monkeypatch, [imp, call])
    asyncio.run(_run_day(engine, fake, day))
    trades = store.trades("paper")
    assert trades and {t["strategy"] for t in trades} == {"TEST_CALL"}, "\n".join(msgs)
    buy = next(m for m in msgs if "BUY" in m)
    assert "TEST_IMPOSSIBLE" in buy and "no strike passed filters" in buy   # reported as checked
    assert "lots within margin" in buy and "Market fit" in buy


def _fixed_fit(monkeypatch):
    """CALLs fit the market (3/3), PUTs do not (0/3); no regime blocking."""
    monkeypatch.setattr(Strategy, "regime_ok", staticmethod(lambda ctx, d, cat: True))
    monkeypatch.setattr(Engine, "market_fit", staticmethod(lambda ctx, d: (3, "all") if d == CE else (0, "none")))


def test_best_market_fit_wins_within_the_same_group(cfg, monkeypatch):
    """Two feasible signals on the same candle: the CALL fits the market better, so it is
    placed even though the PUT has the higher priority."""
    _fixed_fit(monkeypatch)
    put, call = Put(), Call()
    monkeypatch.setattr("sxpro.engine.VERIFIED_INDEX", {put.sid: 1, call.sid: 2})
    engine, fake, day, store, msgs = _engine(cfg, monkeypatch, [put, call])
    asyncio.run(_run_day(engine, fake, day))
    first = store.trades("paper")[0]
    assert first["strategy"] == "TEST_CALL", "\n".join(msgs)


def test_verified_set_beats_added_strategy_even_with_lower_fit(cfg, monkeypatch):
    _fixed_fit(monkeypatch)
    put, call = Put(), Call()
    monkeypatch.setattr("sxpro.engine.VERIFIED_INDEX", {put.sid: 1})   # call enabled later
    engine, fake, day, store, msgs = _engine(cfg, monkeypatch, [put, call])
    asyncio.run(_run_day(engine, fake, day))
    assert store.trades("paper")[0]["strategy"] == "TEST_PUT", "\n".join(msgs)


def test_unknown_live_order_state_never_tries_a_second_strategy(cfg, monkeypatch):
    """A live entry that errors (order may be working at the exchange) must stop the candle;
    a paper error or a clean rejection may fall through to the next candidate."""
    import sxpro.engine as eng
    call = Call()
    engine, fake, day, store, msgs = _engine(cfg, monkeypatch, [call])

    class Boom:
        def __init__(self, text):
            self.text = text

        def buy(self, *a, **k):
            raise RuntimeError(self.text)
    pick = eng.StrikeCandidate("SX1", 1, 80000, CE, day, 20, 0.05, 100, 99, 101, 0.5)
    from sxpro.risk import SizeResult
    plan = eng.EntryPlan(call, Signal(CE, sl_price=1.0), day, pick, SizeResult(2, 40, 50, 9000, 5000), 20)

    async def go(mode, text):
        monkeypatch.setattr(Engine, "broker", lambda self, m: Boom(text))
        return await engine.execute_entry(None, eng.datetime.now(eng.IST), mode, plan, 50000)
    assert asyncio.run(go("live", "read timeout")) == (None, False)
    assert asyncio.run(go("live", "entry rejected: margin")) == (None, True)
    assert asyncio.run(go("paper", "no ask price")) == (None, True)


def test_tuning_overrides_merge_per_key(monkeypatch):
    from sxpro.strategies import tuning
    out = tuning.merged({"A": {"priority": 1, "x": 1}}, {"A": {"x": 2}, "B": {"y": 3}})
    assert out == {"A": {"priority": 1, "x": 2}, "B": {"y": 3}}


def test_kite_account_is_pinned(cfg, tmp_path):
    from sxpro.kite_service import KiteService, TokenError

    class FakeKC:
        def __init__(self):
            self.access_token, self.user = None, "AB1234"

        def set_access_token(self, t):
            self.access_token = t

        def profile(self):
            return {"user_id": self.user, "user_name": "x"}

        def generate_session(self, rt, api_secret):
            return {"access_token": "tok-" + rt, "user_id": self.user}

        def invalidate_access_token(self, t):
            self.invalidated = t
    ks = KiteService(cfg)
    ks.kite = FakeKC()
    assert ks.activate("good") and ks.expected_user() == "AB1234"      # first login pins AB1234
    ks.kite.user = "ZZ9999"
    with pytest.raises(TokenError):
        ks.exchange_request_token("r1")                                 # stranger's login rejected
    assert ks.kite.invalidated == "tok-r1" and ks.kite.access_token == "good"
    assert not ks.activate("stolen")                                    # nor their token
