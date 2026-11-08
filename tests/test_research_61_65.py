"""Research strategies 61-65: noise band maths, priority ordering, signals on synthetic days."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from sxpro.market import build_context
from sxpro.strategies import ALL_STRATEGIES
from sxpro.strategies.base import CE, PE
from sxpro.strategies.catalog import STRATEGIES_61_65, noise_sigma

from .fakes import synthetic_candles


def test_noise_sigma_matches_definition():
    df = synthetic_candles(16, seed=3)
    days = sorted(set(df.index.date))
    today = days[-1]
    sig = noise_sigma(df, today, 14)
    assert sig is not None and sig.shape == (75,)
    rows = []
    for d in days[-15:-1]:
        g = df[df.index.date == d]
        rows.append(np.abs(g["close"].to_numpy() / g["open"].iloc[0] - 1))
    assert np.allclose(sig, np.mean(rows, axis=0))
    assert noise_sigma(df, days[5], 14) is None   # not enough history


def test_research_strategies_run_first():
    order = sorted(ALL_STRATEGIES, key=lambda s: s.priority)
    assert [s.sid for s in order[:5]] == [s.sid for s in STRATEGIES_61_65]
    assert all(s.priority == 10 for s in STRATEGIES_61_65)


@pytest.mark.parametrize("seed,drift", [(1, 0.0012), (2, -0.0012), (3, 0.0)])
def test_research_signals_on_trend_days(seed, drift):
    """On a strongly trending synthetic day the breakout rules fire in the trend direction;
    every signal and exit check runs without error."""
    df = synthetic_candles(18, seed=seed)
    days = sorted(set(df.index.date))
    day = days[-1]
    today = df[df.index.date == day].copy()
    steps = np.cumprod(np.full(len(today), 1 + drift))
    base = float(today["open"].iloc[0])
    for col in ("open", "high", "low", "close"):
        today[col] = base * steps * (today[col] / today[col].iloc[0]) ** 0.05
    today["high"] = today[["open", "high", "close"]].max(axis=1) * 1.0003
    today["low"] = today[["open", "low", "close"]].min(axis=1) * 0.9997
    df = pd.concat([df[df.index.date < day], today])
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = daily.iloc[-2]
    sigma = noise_sigma(df, day)
    seen = {}
    for i in range(1, len(today)):
        part = df.iloc[: len(df) - len(today) + i + 1]
        now = part.index[-1].to_pydatetime() + timedelta(minutes=5)
        ctx = build_context(part, now, {"open": prev.open, "high": prev.high, "low": prev.low, "close": prev.close},
                            25.0, day + timedelta(days=1), {"noise": sigma})
        for s in STRATEGIES_61_65:
            if s.in_window(ctx):
                sig = s.entry(ctx)
                if sig is not None:
                    seen.setdefault(s.sid, sig.direction)
                    pos = {"direction": sig.direction, "entry_time": now.isoformat(), "meta": sig.meta}
                    s.exit_on_close(ctx, pos)
    if drift > 0:
        assert seen and all(d == CE for d in seen.values())
    elif drift < 0:
        assert seen and all(d == PE for d in seen.values())
