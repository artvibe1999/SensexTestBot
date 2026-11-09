"""2026-11-09 catalog review: 12 retired strategies off by default (and once on existing
installs), ATR buffer on wick / pivot stops of strategies 02, 09, 23, 44."""
import pandas as pd
import pytest

from sxpro.config import Config
from sxpro.engine import Engine
from sxpro.store import Store
from sxpro.strategies import STRATEGY_MAP
from sxpro.strategies.base import CE, PE
from sxpro.strategies.catalog import InsideBarBreakout, sweep_buffer
from sxpro.strategies.tuning import RETIRED, RETIRED_FLAG, VERIFIED_ORDER

from .fakes import FakeKite, synthetic_candles


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


def _engine(cfg, store):
    df = synthetic_candles(2)
    return Engine(cfg, store, FakeKite(df, df.index[-1].date()))


def test_retired_ids_exist_and_exclude_verified():
    assert len(RETIRED) == 12 and all(sid in STRATEGY_MAP for sid in RETIRED)
    assert not set(RETIRED) & set(VERIFIED_ORDER)


def test_fresh_install_disables_retired(cfg):
    store = Store(cfg.db_path)
    eng = _engine(cfg, store)
    assert set(store.get("disabled")) == set(RETIRED) and store.get(RETIRED_FLAG)
    assert not {s.sid for s in eng.enabled_strategies()} & set(RETIRED)


def test_existing_install_gets_retired_once_then_respects_enable(cfg):
    store = Store(cfg.db_path)
    store.set("disabled", ["SENSEX_TRAP_02"])          # older install, flag not set
    _engine(cfg, store)
    assert set(store.get("disabled")) == set(RETIRED) | {"SENSEX_TRAP_02"}
    # the user switches one back on with /enable; a restart must not undo it
    store.set("disabled", sorted(set(store.get("disabled")) - {"SENSEX_FIB_19"}))
    _engine(cfg, store)
    assert "SENSEX_FIB_19" not in store.get("disabled")


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
