"""Research strategies 66-79 and the trend-day tuning gates."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from sxpro.market import build_context
from sxpro.strategies import STRATEGY_MAP
from sxpro.strategies.base import CE, PE, Signal
from sxpro.strategies.catalog_research import noise_sigma
from sxpro.strategies.catalog_research2 import STRATEGIES_66_79

from .fakes import synthetic_candles


def _trend_df(seed, drift):
    df = synthetic_candles(18, seed=seed)
    day = sorted(set(df.index.date))[-1]
    today = df[df.index.date == day].copy()
    steps = np.cumprod(np.full(len(today), 1 + drift))
    base = float(today["open"].iloc[0])
    for col in ("open", "high", "low", "close"):
        today[col] = base * steps * (today[col] / today[col].iloc[0]) ** 0.05
    today["high"] = today[["open", "high", "close"]].max(axis=1) * 1.0003
    today["low"] = today[["open", "low", "close"]].min(axis=1) * 0.9997
    return pd.concat([df[df.index.date < day], today]), day, len(today)


def test_ids_registered():
    assert len(STRATEGIES_66_79) == 14
    assert len({s.sid for s in STRATEGIES_66_79}) == 14
    assert all(s.sid in STRATEGY_MAP and s.priority == 10 for s in STRATEGIES_66_79)


@pytest.mark.parametrize("seed,drift", [(1, 0.0012), (2, -0.0012), (3, 0.0), (4, 0.0006)])
def test_signals_follow_the_trend(seed, drift):
    df, day, n = _trend_df(seed, drift)
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = daily.iloc[-2]
    aux = {"noise": noise_sigma(df, day), "daily": daily[daily.index.date < day]}
    seen = {}
    for i in range(1, n):
        part = df.iloc[: len(df) - n + i + 1]
        now = part.index[-1].to_pydatetime() + timedelta(minutes=5)
        ctx = build_context(part, now, {"open": prev.open, "high": prev.high, "low": prev.low, "close": prev.close},
                            25.0, day + timedelta(days=1), aux)
        for s in STRATEGIES_66_79:
            if not s.in_window(ctx):
                continue
            sig = s.entry(ctx)
            if sig is None:
                continue
            seen.setdefault(s.sid, sig.direction)
            if sig.sl_price is not None:
                assert (sig.sl_price < ctx.last["close"]) == (sig.direction == CE)
            s.exit_on_close(ctx, {"direction": sig.direction, "entry_time": now.isoformat(), "meta": sig.meta})
    if drift > 0.001:
        assert seen and all(d == CE for d in seen.values())
    elif drift < -0.001:
        assert seen and all(d == PE for d in seen.values())


def test_trend_day_gates():
    df, day, n = _trend_df(1, 0.0012)
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = daily.iloc[-2]
    part = df.iloc[: len(df) - n + 40]
    ctx = build_context(part, part.index[-1].to_pydatetime() + timedelta(minutes=5),
                        {"open": prev.open, "high": prev.high, "low": prev.low, "close": prev.close}, 25.0,
                        day + timedelta(days=1), {"noise": noise_sigma(df, day)})
    s = STRATEGY_MAP["SENSEX_VWAP_03"]
    old = s.tune
    try:
        s.tune = {"vwap_side": True}
        assert s.apply_tuning(ctx, Signal(CE, sl_price=1.0)) is not None
        assert s.apply_tuning(ctx, Signal(PE, sl_price=1e9)) is None
        s.tune = {"day_move": 0.5}
        assert s.apply_tuning(ctx, Signal(CE, sl_price=1.0)) is None
        s.tune = {"noise_k": 0.5}
        assert s.apply_tuning(ctx, Signal(CE, sl_price=1.0)) is not None
        assert s.apply_tuning(ctx, Signal(PE, sl_price=1e9)) is None
        s.tune = {"hold_close": True}
        assert s.apply_tuning(ctx, Signal(CE, sl_price=1.0, target=1e9)).target is None
    finally:
        s.tune = old
