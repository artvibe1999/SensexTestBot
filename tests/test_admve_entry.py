"""ADMVE (SENSEX_ADMVE_80): entry logic on crafted candles, score threshold, stable setup
key, default-off on fresh and existing installs, feed needs and ranking after the verified set."""
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from sxpro.config import IST, Config
from sxpro.engine import KNOWN_STRATEGIES_KEY, Engine
from sxpro.liquidity import analyze_liquidity
from sxpro.market import BULL
from sxpro.store import Store
from sxpro.strategies import ALL_STRATEGIES, STRATEGY_MAP
from sxpro.strategies.admve import AdaptiveDirectionalMomentum
from sxpro.strategies.base import CE
from sxpro.strategies.tuning import DEFAULT_DENY_FLAG, VERIFIED_ORDER

from .fakes import FakeKite, synthetic_candles

SID = "SENSEX_ADMVE_80"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


def _engine(cfg, store):
    df = synthetic_candles(2)
    return Engine(cfg, store, FakeKite(df, df.index[-1].date()))


def _bull_ctx(atr_last=44.0, rvol_last=1.5, zones=None):
    """40 rising 5m bars ending in a strong breakout candle, every bullish gate satisfied."""
    idx = pd.date_range(datetime(2026, 11, 16, 9, 15, tzinfo=IST), periods=40, freq="5min")
    close = 80000 + 10.0 * np.arange(40)
    close[-1] = close[-2] + 60
    opn = np.r_[close[0] - 5, close[:-1]]
    df = pd.DataFrame({
        "open": opn, "close": close, "high": close + 2, "low": opn - 1, "volume": 1000.0,
        "atr": 40.0, "adx": np.linspace(24, 30, 40), "plus_di": 30.0, "minus_di": 15.0,
        "ema9": close - 20, "ema21": close - 40, "ema50": close - 80, "vwap": close - 100,
        "body_pct": 0.9, "rvol": 1.2,
    }, index=idx)
    df.iloc[-1, df.columns.get_loc("atr")] = atr_last
    df.iloc[-1, df.columns.get_loc("rvol")] = rvol_last
    idx15 = pd.date_range(idx[-1] - pd.Timedelta(minutes=15 * 35), periods=35, freq="15min")
    df15 = pd.DataFrame({"ema9": 2.0, "ema21": 1.0, "plus_di": 30.0, "minus_di": 10.0}, index=idx15)
    liq = {"available": True, "score": 60.0, "event": "bullish_breakout", "direction": 1,
           "zones": zones or []}
    return SimpleNamespace(df=df, df15=df15, n_today=40, regime=BULL, regime_detail={},
                           aux={"liquidity": liq}, last=df.iloc[-1])


def test_trend_breakout_fires_with_stable_setup_key():
    sig = AdaptiveDirectionalMomentum().entry(_bull_ctx())
    assert sig is not None and sig.direction == CE
    assert sig.setup_key == "ADMVE:CE:breakout"            # no timestamp: no re-entry every bar
    close = 80000 + 10.0 * 38 + 60
    assert sig.sl_price == pytest.approx(close - 1.5 * 44.0)
    assert sig.meta["admve_score"] == 95                   # 70 + ATR 10 + volume 5 + room 10


def test_score_threshold_filters_signals_without_optional_evidence():
    # no ATR expansion, a resistance 0.5 ATR above (no room): 70 + volume 5 = 75 < 80
    close = 80000 + 10.0 * 38 + 60
    zones = [{"kind": "resistance", "price": close + 20, "strength": 55, "source": "x"}]
    ctx = _bull_ctx(atr_last=40.0, zones=zones)
    assert AdaptiveDirectionalMomentum().entry(ctx) is None
    tuned = AdaptiveDirectionalMomentum()
    tuned.tune = {"min_score": 75}
    assert tuned.entry(ctx) is not None


def test_no_trigger_no_entry():
    ctx = _bull_ctx(rvol_last=1.0)                          # breakout without volume is no trigger
    ctx.aux["liquidity"]["event"] = "none"
    assert AdaptiveDirectionalMomentum().entry(ctx) is None


def test_admve_starts_disabled_on_fresh_install(cfg):
    store = Store(cfg.db_path)
    eng = _engine(cfg, store)
    assert [s.sid for s in eng.enabled_strategies()] == VERIFIED_ORDER
    assert SID in store.get(KNOWN_STRATEGIES_KEY)


def test_admve_starts_disabled_on_existing_install_then_enable_is_kept(cfg):
    """An install from before ADMVE: its disabled list does not name ADMVE."""
    store = Store(cfg.db_path)
    store.set(DEFAULT_DENY_FLAG, True)
    store.set("disabled", sorted(s.sid for s in ALL_STRATEGIES
                                 if s.sid not in VERIFIED_ORDER and s.sid != SID))
    assert SID not in [s.sid for s in _engine(cfg, store).enabled_strategies()]
    store.set("disabled", sorted(set(store.get("disabled")) - {SID}))       # /enable ADMVE_80
    enabled = [s.sid for s in _engine(cfg, store).enabled_strategies()]
    assert enabled == VERIFIED_ORDER + [SID]


def test_liquidity_feeds_only_when_admve_enabled_and_admve_ranks_after_verified(cfg):
    store = Store(cfg.db_path)
    eng = _engine(cfg, store)
    assert not {"liquidity", "futures_depth"} & eng._needs()
    store.set("disabled", sorted(set(store.get("disabled")) - {SID}))
    assert {"liquidity", "futures_depth"} <= eng._needs()
    assert eng.strategy_rank(STRATEGY_MAP[SID])[0] == 1
    assert all(eng.strategy_rank(STRATEGY_MAP[s])[0] == 0 for s in VERIFIED_ORDER)


def test_liquidity_score_ignores_futures_depth():
    df = synthetic_candles(2)
    from sxpro.market import build_context
    day = df[df.index.date == df.index[-1].date()]
    prev = df[df.index.date < df.index[-1].date()]
    ctx = build_context(pd.concat([prev, day.iloc[:30]]), day.index[29],
                        {"open": prev.open.iloc[0], "high": prev.high.max(), "low": prev.low.min(),
                         "close": prev.close.iloc[-1]})
    depth = {"depth": {"buy": [{"quantity": 900}], "sell": [{"quantity": 100}]}}
    a, b = analyze_liquidity(ctx, None), analyze_liquidity(ctx, depth)
    assert a["score"] == b["score"] and b["obi"] is not None
