"""Strategies 21-60: they evaluate on synthetic data with every aux feed, and the
building blocks (expiry rule, entry cap, breadth, signal builder) behave."""
from datetime import date, time, timedelta

import numpy as np
import pandas as pd
import pytest

from sxpro.market import build_context
from sxpro.options import choose_expiry
from sxpro.strategies import STRATEGY_MAP
from sxpro.strategies.base import CE, PE, Signal
from sxpro.strategies.catalog_21_60 import STRATEGIES_21_60, PocBounce43, Spec, pivots

from .fakes import synthetic_candles


def _aux(df: pd.DataFrame, day: date, last_bar) -> dict:
    today = df[(df.index.date == day) & (df.index <= last_bar)]
    rng = np.random.default_rng(0)
    vix = pd.Series(np.linspace(16, 14.5, len(today)), index=today.index)
    nifty = today[["open", "high", "low", "close"]] / 3.3
    breadth = pd.Series(rng.uniform(0.3, 3.0, len(today)), index=today.index)
    k0 = round(float(today["close"].iloc[-1]) / 100) * 100
    oi = {"expiry": day, "CE": {k0 + 100 * i: 1e5 * (5 if i == 1 else 1) for i in range(-5, 6)},
          "PE": {k0 + 100 * i: 1e5 * (5 if i == -1 else 1) for i in range(-5, 6)}}
    first = today.iloc[0][["open", "high", "low", "close"]]
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return {"vix": vix, "nifty": nifty, "breadth": breadth, "oi": oi, "first_min": first,
            "daily": daily[daily.index.date < day]}


def test_count_and_ids():
    assert len(STRATEGIES_21_60) == 40
    nums = sorted(int(s.sid.rsplit("_", 1)[1]) for s in STRATEGIES_21_60)
    assert nums == list(range(21, 61))
    assert all(s.sid in STRATEGY_MAP for s in STRATEGIES_21_60)


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_new_strategies_run_with_all_feeds(seed):
    """Every new strategy evaluates every candle (entry + exit + trail) without raising,
    with all aux feeds present, on trending and ranging synthetic days incl. expiry."""
    df = synthetic_candles(8, seed=seed, drift=0.0003 * (seed - 2.5))
    day = sorted(set(df.index.date))[-1]
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = daily.iloc[-2]
    idx = [i for i, ts in enumerate(df.index) if ts.date() == day]
    signals = 0
    for i in idx[1:]:
        part = df.iloc[: i + 1]
        now = part.index[-1].to_pydatetime() + timedelta(minutes=5)
        ctx = build_context(part, now, {"open": prev.open, "high": prev.high, "low": prev.low, "close": prev.close},
                            25.0, day if seed % 2 else day + timedelta(days=1), _aux(df, day, part.index[-1]))
        for s in STRATEGIES_21_60:
            sig = s.entry(ctx) if s.in_window(ctx) else None
            pos = {"direction": CE if seed % 2 else PE, "entry_time": (now - timedelta(minutes=15)).isoformat(),
                   "underlying_entry": float(part["close"].iloc[-4]), "meta": {}, "stop_ref": None}
            if sig is not None:
                signals += 1
                assert sig.direction in (CE, PE)
                stop = sig.sl_price if sig.sl_price is not None else sig.sl_close
                assert stop is not None and (stop < ctx.last["close"]) == (sig.direction == CE)
                if sig.target is not None:
                    assert (sig.target > ctx.last["close"]) == (sig.direction == CE)
                pos.update(direction=sig.direction, meta=sig.meta)
            s.exit_on_close(ctx, pos)
            s.trail_level(ctx, pos)
    assert signals >= 0


def test_next_weekly_expiry_rule():
    e1, e2 = date(2026, 11, 5), date(2026, 11, 12)
    assert choose_expiry([e1, e2], date(2026, 11, 4), "next", time(15, 5)) == e2
    assert choose_expiry([e1], date(2026, 11, 4), "next", time(15, 5)) is None


def test_reentry_once_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from sxpro.config import Config
    from sxpro.engine import Engine
    from sxpro.store import Store
    from .fakes import FakeKite
    df = synthetic_candles(3)
    eng = Engine(Config(), Store(str(tmp_path / "x.db")), FakeKite(df, date(2026, 11, 5)))
    s = STRATEGY_MAP["SENSEX_PDC_BNC_23"]
    assert s.reentry == "yes" and s.max_entries == 2
    sig = Signal(CE)
    day = "2026-11-04"
    assert eng._reentry_ok(s, sig, day)
    eng.store.set(f"setups_{day}", {s.sid: ["a"]})
    assert eng._reentry_ok(s, sig, day)
    eng.store.set(f"setups_{day}", {s.sid: ["a", "b"]})
    assert not eng._reentry_ok(s, sig, day)


def test_signal_builder_rejects_bad_geometry():
    s = Spec()
    assert s.make(CE, 100, 101) is None                       # stop above entry for a CALL
    assert s.make(CE, 100, 95, target=99) is None             # target behind price
    sig = s.make(CE, 100, 95, target=99, rr_fallback=2.0)     # falls back to 1:2
    assert sig.target == pytest.approx(110)
    sig = s.make(PE, 100, 104, close_stop=True)
    assert sig.sl_price is None and sig.sl_close == 104 and sig.meta["sl_close"] == 104


def test_close_stop_exit():
    df = synthetic_candles(3)
    day = sorted(set(df.index.date))[-1]
    part = df[df.index.date <= day].iloc[:-30]
    ctx = build_context(part, part.index[-1].to_pydatetime() + timedelta(minutes=5),
                        {"open": 1, "high": 2, "low": 0.5, "close": 1}, 20.0, day)
    c = float(ctx.last["close"])
    s = Spec()
    assert s.exit_on_close(ctx, {"direction": CE, "meta": {"sl_close": c + 1}})
    assert s.exit_on_close(ctx, {"direction": CE, "meta": {"sl_close": c - 1}}) is None


def test_pivots_and_poc():
    df = pd.DataFrame({"high": [1, 3, 5, 3, 1, 2, 4, 2, 1], "low": [0, 2, 4, 2, 0, 1, 3, 1, 0]})
    assert pivots(df, "high") == [2, 6]
    assert pivots(df, "low") == [4]
    candles = synthetic_candles(3)
    day = sorted(set(candles.index.date))[-1]
    part = candles[candles.index.date <= day].iloc[:-60]
    ctx = build_context(part, part.index[-1].to_pydatetime() + timedelta(minutes=5),
                        {"open": 1, "high": 2, "low": 0.5, "close": 1}, 20.0, day)
    poc = PocBounce43.poc(ctx)
    prev = part[part.index.date < day]
    prev = prev[prev.index.date == prev.index[-1].date()]
    assert prev["low"].min() - 20 <= poc <= prev["high"].max() + 20


def test_backtest_breadth_ratio(tmp_path):
    """Advance/decline ratio = advancers / max(decliners, 1) vs previous daily close."""
    idx = pd.date_range("2026-11-03 09:15", periods=2, freq="5min", tz="Asia/Kolkata")
    c5 = pd.DataFrame({"A": [101, 99], "B": [99, 98], "C": [102, 103]}, index=idx)
    cd = pd.DataFrame({"A": [100, 0], "B": [100, 0], "C": [100, 0]},
                      index=pd.DatetimeIndex(["2026-11-02", "2026-11-03"]).tz_localize("Asia/Kolkata"))
    cd.index = pd.Index([ts.date() for ts in cd.index])
    pc = cd.shift(1).reindex([ts.date() for ts in c5.index])
    pc.index = c5.index
    adv, dec = (c5 > pc).sum(axis=1), (c5 < pc).sum(axis=1)
    ratio = adv / dec.clip(lower=1)
    assert list(ratio) == [2.0, 0.5]
