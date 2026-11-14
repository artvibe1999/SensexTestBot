"""Entry timing guards: extension / 30-min run filters and pullback parking."""
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from sxpro.config import IST, Config
from sxpro.engine import Engine
from sxpro.strategies.base import CE, Signal


def _engine(**cfg):
    eng = Engine.__new__(Engine)
    eng.cfg = replace(Config(), **cfg)
    eng.pending = {}
    return eng


def _ctx(close, ema21=1000.0, atr=10.0):
    closes = [1000.0] * 7 + [close]
    today = pd.DataFrame({"close": closes})
    return SimpleNamespace(last=pd.Series({"close": close, "ema21": ema21, "atr": atr}), today=today)


NOW = datetime(2026, 11, 16, 10, 0, tzinfo=IST)
PE = "PE"


def test_extension_filter_skips_only_the_extended_side():
    eng = _engine(entry_ext_max_atr=2.0)
    s = SimpleNamespace(sid="X")
    ctx = _ctx(close=1025.0)  # 2.5 ATR above EMA21
    assert eng._timing_guard(ctx, NOW, [(s, Signal(direction=CE))]) == []
    kept = eng._timing_guard(ctx, NOW, [(s, Signal(direction=PE))])
    assert len(kept) == 1  # a PE is not extended when price is above EMA21
    assert len(eng._timing_guard(_ctx(close=1015.0), NOW, [(s, Signal(direction=CE))])) == 1


def test_guards_off_by_default_keep_every_signal():
    eng = _engine()
    s = SimpleNamespace(sid="X")
    assert len(eng._timing_guard(_ctx(close=1100.0), NOW, [(s, Signal(direction=CE))])) == 1


def test_pullback_parks_signal_at_level():
    eng = _engine(entry_pullback_atr=0.5, entry_pullback_min=30)
    s = SimpleNamespace(sid="X")
    assert eng._timing_guard(_ctx(close=1010.0), NOW, [(s, Signal(direction=CE, sl_price=990.0))]) == []
    p = eng.pending["X"]
    assert p["level"] == 1005.0 and p["stop"] == 990.0 and p["d"] == 1
