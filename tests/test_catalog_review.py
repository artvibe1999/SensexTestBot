"""Catalog review: default deny except the ADMVE candidate and six verified strategies;
12 retired strategies flagged, ATR buffer on selected wick / pivot stops."""
import pandas as pd
import pytest

from sxpro.config import Config
from sxpro.engine import Engine
from sxpro.store import Store
from sxpro.strategies import ALL_STRATEGIES, STRATEGY_MAP
from sxpro.strategies.base import CE, PE
from sxpro.market import BEAR, BULL, NEUTRAL, SIDEWAYS
from sxpro.strategies.catalog import InsideBarBreakout, SupertrendPullback, sweep_buffer
from sxpro.strategies.tuning import DEFAULT_DENY_FLAG, RETIRED, VERIFIED_ORDER

from .fakes import FakeKite, synthetic_candles

LIVE_EXTRAS = ["SENSEX_VWAP_03", "SENSEX_GAP_07", "SENSEX_VOL_08", "SENSEX_SUP_10", "SENSEX_0DTE_12",
               "SENSEX_DOJI_15", "SENSEX_VWAP_X_16", "SENSEX_MCD_18", "SENSEX_FIB_19"]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


def _engine(cfg, store):
    df = synthetic_candles(2)
    return Engine(cfg, store, FakeKite(df, df.index[-1].date()))


def _enabled(eng):
    return [s.sid for s in eng.enabled_strategies()]


def test_retired_ids_exist_and_exclude_verified():
    assert len(RETIRED) == 12 and all(sid in STRATEGY_MAP for sid in RETIRED)
    assert not set(RETIRED) & set(VERIFIED_ORDER)


def test_fresh_install_enables_admve_and_verified_six(cfg):
    store = Store(cfg.db_path)
    eng = _engine(cfg, store)
    expected = ["SENSEX_ADMVE_80"] + VERIFIED_ORDER
    assert _enabled(eng) == expected and store.get(DEFAULT_DENY_FLAG)
    assert len(store.get("disabled")) == len(ALL_STRATEGIES) - len(expected)


def test_live_install_drops_extras_once_then_respects_enable(cfg):
    """The 9 Nov live state (six + 9 extras) becomes the six on the next boot; a strategy
    enabled afterwards with /enable survives restarts."""
    store = Store(cfg.db_path)
    keep = set(VERIFIED_ORDER) | set(LIVE_EXTRAS)
    store.set("disabled", sorted(s.sid for s in ALL_STRATEGIES if s.sid not in keep))   # flag not set
    expected = ["SENSEX_ADMVE_80"] + VERIFIED_ORDER
    assert _enabled(_engine(cfg, store)) == expected
    store.set("disabled", sorted(set(store.get("disabled")) - {"SENSEX_VWAP_03"}))      # /enable 03
    assert _enabled(_engine(cfg, store)) == expected + ["SENSEX_VWAP_03"]


def test_verified_strategy_disabled_by_user_stays_disabled(cfg):
    store = Store(cfg.db_path)
    store.set("disabled", ["SENSEX_HLBRK_66"])
    assert _enabled(_engine(cfg, store)) == ["SENSEX_ADMVE_80"] + VERIFIED_ORDER[:5]


def test_sweep_buffer():
    assert sweep_buffer({"atr": 60.0}) == 30.0
    assert sweep_buffer({"atr": float("nan")}) == 0.0


def _row(o, h, l, c, **kw):
    return pd.Series({"open": o, "high": h, "low": l, "close": c, "volume": kw.get("volume", 100.0),
                      "adx": 25.0, "ema9": kw.get("ema9", 0.0), "atr": kw.get("atr", 60.0)})


class _Ctx:
    def __init__(self, rows):
        self.rows = rows   # newest first
        self.df = pd.DataFrame(rows[::-1], index=pd.date_range("2026-11-09 10:00", periods=len(rows), freq="5min"))

    def c(self, back=0):
        return self.rows[back]


def test_inside_bar_stop_sits_half_atr_beyond_the_wick():
    s = InsideBarBreakout()
    mother = _row(100, 120, 80, 110, volume=100, ema9=100)
    ib = _row(105, 115, 90, 108, ema9=101)
    up = _row(110, 130, 108, 125, volume=200, ema9=103)
    sig = s.entry(_Ctx([up, ib, mother, _row(100, 101, 99, 100, ema9=99)]))
    assert sig.direction == CE and sig.sl_price == pytest.approx(90 - 30)       # ib low - 0.5 x ATR
    dn = _row(90, 92, 70, 75, volume=200, ema9=97)
    sig = s.entry(_Ctx([dn, ib, mother, _row(100, 101, 99, 100, ema9=99)]))
    assert sig.direction == PE and sig.sl_price == pytest.approx(115 + 30)      # ib high + 0.5 x ATR


class _StCtx:
    """Minimal context for SUP_10: a bearish Supertrend (st 100) touched by a shooting star."""
    def __init__(self, regime):
        self.regime = regime
        self.df = pd.DataFrame({"st_dir": [-1] * 13, "high": [99.0] * 13, "low": [80.0 + i for i in range(13)]})
        self.rows = [pd.Series({"open": 95.0, "high": 100.0, "low": 93.5, "close": 94.0, "volume": 200.0,
                                "st": 100.0, "st_dir": -1, "range": 6.5, "body": 1.0,
                                "upper_wick": 5.0, "upper_wick_pct": 5 / 6.5,
                                "lower_wick": 0.5, "lower_wick_pct": 0.5 / 6.5}),
                     pd.Series({"volume": 100.0})]

    def c(self, back=0):
        return self.rows[back]

    def swing_low(self, lookback, skip=1):
        return float(self.df["low"].iloc[-lookback - skip:-skip].min())

    swing_high = swing_low


@pytest.mark.parametrize("regime,allowed", [(BEAR, True), (NEUTRAL, False), (SIDEWAYS, False), (BULL, False)])
def test_supertrend_pe_needs_bearish_regime(regime, allowed):
    sig = SupertrendPullback().entry(_StCtx(regime))
    assert (sig is not None and sig.direction == PE) if allowed else sig is None
