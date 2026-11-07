import asyncio
import json
from datetime import date, datetime, time, timedelta

import pytest

from sxpro import indicators as ind
from sxpro.config import IST, Config
from sxpro.engine import Engine
from sxpro.market import build_context
from sxpro.options import (StrikeCandidate, bs_delta, bs_price, choose_expiry, implied_vol, select_strike)
from sxpro.risk import RiskManager
from sxpro.store import Store
from sxpro.strategies import ALL_STRATEGIES
from sxpro.strategies.base import CE, Signal, Strategy

from .fakes import FakeKite, synthetic_candles


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_CAPITAL", "50000")
    return Config()


def test_indicators_shapes():
    df = synthetic_candles(5)
    e = ind.enrich(df)
    for col in ("ema9", "vwap", "adx", "st", "psar", "macd", "stoch_k", "bb_upper", "kc_upper", "rvol", "wma13"):
        assert col in e and e[col].iloc[-1] == e[col].iloc[-1], col  # not NaN
    # VWAP resets daily: first candle VWAP == typical price
    first = e[e.index.date == e.index[-1].date()].iloc[0]
    assert first["vwap"] == pytest.approx((first["high"] + first["low"] + first["close"]) / 3)


def test_black_scholes_roundtrip():
    p = bs_price(80000, 80000, 5 / 365, 0.065, 0.15, True)
    iv = implied_vol(p, 80000, 80000, 5 / 365, 0.065, True)
    assert iv == pytest.approx(0.15, abs=1e-3)
    assert 0.45 < bs_delta(80000, 80000, 5 / 365, 0.065, 0.15, True) < 0.56


def test_expiry_rules():
    e1, e2 = date(2026, 11, 5), date(2026, 11, 12)
    assert choose_expiry([e1, e2], date(2026, 11, 4), "weekly", time(10)) == e1
    assert choose_expiry([e1, e2], e1, "weekly", time(10)) == e2          # 0DTE -> roll
    assert choose_expiry([e1, e2], e1, "0dte", time(14)) == e1
    assert choose_expiry([e1, e2], date(2026, 11, 4), "0dte", time(14)) is None
    assert choose_expiry([e1, e2], e1, "weekly_2pm", time(13)) == e1
    assert choose_expiry([e1, e2], e1, "weekly_2pm", time(14, 30)) == e2


def test_strike_selection_filters():
    exp = date(2026, 11, 5)
    mk = lambda k, d, p, b, a: StrikeCandidate(f"S{k}", k, k, "CE", exp, 20, 0.05, p, b, a, d)
    cands = [mk(1, 0.5, 300, 299, 301), mk(2, 0.45, 240, 239, 241), mk(3, 0.3, 150, 149, 151)]
    pick, _ = select_strike(cands, 0.4, 0.6, 0.5, 200, 400, 250, 0.01)
    assert pick.tradingsymbol == "S2"  # S1 not affordable
    pick, why = select_strike(cands, 0.4, 0.6, 0.5, 200, 400, 100, 0.01)
    assert pick is None and "affordable" in why


def test_sizing_auto_and_fixed(cfg):
    rm = RiskManager(cfg, Store(cfg.db_path))
    # 50k margin x 90% = 45000 alloc, lot 20, premium 120 -> floor(45000/2400) = 18 lots
    r = rm.size("paper", 50000, 50000, 120, 20, 0.10, "auto", 102)
    assert r.lots == 18 and r.qty == 360
    # 10% loss cap: 5000/360 = 13.89/unit -> stop 106.11 is tighter than the strategy's 102
    assert r.hard_stop == pytest.approx(120 - 5000 / 360, abs=0.01)
    # 0DTE (capital_pct 0.05) deploys half: 22500/2400 -> 9 lots
    assert rm.size("paper", 50000, 50000, 120, 20, 0.05, "auto", None).lots == 9
    # fixed lots honoured within the 90% margin; cap stop = 120 - 5000/60
    r = rm.size("paper", 50000, 50000, 120, 20, 0.10, 3, None)
    assert r.lots == 3 and r.hard_stop == pytest.approx(120 - 5000 / 60, abs=0.01)
    # fixed lots beyond 90% of margin are cut down to what fits
    assert rm.size("paper", 50000, 50000, 120, 20, 0.10, 40, None).lots == 18
    # insufficient margin
    assert rm.size("paper", 50000, 1000, 120, 20, 0.10, 2, None).lots == 0


def test_risk_limits(cfg):
    store = Store(cfg.db_path)
    rm = RiskManager(cfg, store)
    now = datetime(2026, 11, 4, 11, 0, tzinfo=IST)
    for i in range(4):
        store.record_trade({"position_id": str(i), "mode": "paper", "strategy": "X", "symbol": "S", "option_type": "CE",
                            "qty": 20, "entry_price": 100, "exit_price": 90, "gross_pnl": -200, "charges": 0,
                            "net_pnl": -200, "entry_time": now.isoformat(), "exit_time": now.isoformat(),
                            "exit_reason": "t", "trade_day": now.date().isoformat()})
        rm.on_trade_closed("paper", -200)
    ok, why = rm.can_open("paper", 50000, now)
    assert not ok and "cool-off" in why
    assert rm.paper_balance() == pytest.approx(49200)


def test_all_strategies_run_on_synthetic_data():
    """Every strategy must evaluate every candle without raising."""
    for seed in (1, 2, 3):
        df = synthetic_candles(6, seed=seed, drift=0.0002 * (seed - 2))
        days = sorted(set(df.index.date))
        last_day = days[-1]
        daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        prev = daily.iloc[-2]
        today_idx = [i for i, ts in enumerate(df.index) if ts.date() == last_day]
        for i in today_idx[2:]:
            part = df.iloc[: i + 1]
            ctx = build_context(part, part.index[-1].to_pydatetime() + timedelta(minutes=5),
                                {"open": prev.open, "high": prev.high, "low": prev.low, "close": prev.close},
                                25.0, last_day)
            for s in ALL_STRATEGIES:
                if s.in_window(ctx):
                    s.entry(ctx)


async def _run_day(engine: Engine, fake: FakeKite, day: date, step_s: int = 30):
    t = datetime.combine(day, time(9, 15), tzinfo=IST)
    end = datetime.combine(day, time(15, 40), tzinfo=IST)
    while t <= end:
        fake.now = t
        await engine.tick(t)
        t += timedelta(seconds=step_s)


class AlwaysCall(Strategy):
    sid, name = "TEST_ALWAYS", "test"
    start, end = time(10, 0), time(10, 5)
    prem_min, prem_max = 1, 5000
    delta_min, delta_max = 0.3, 0.7

    def entry(self, ctx):
        c = float(ctx.last["close"])
        return Signal(CE, sl_price=c - 400, target=c + 1, book_fraction=0.5, note="forced")


def test_engine_paper_day_lifecycle(cfg, monkeypatch):
    df = synthetic_candles(6, seed=7, drift=0.0003)
    day = sorted(set(df.index.date))[-1]
    fake = FakeKite(df, expiry=day + timedelta(days=1))
    store = Store(cfg.db_path)
    engine = Engine(cfg, store, fake)
    msgs: list[str] = []

    async def notify(text):
        msgs.append(text)
    engine.notify = notify
    import sxpro.engine as eng
    strat = AlwaysCall()
    monkeypatch.setattr(eng, "STRATEGY_MAP", {**eng.STRATEGY_MAP, strat.sid: strat})
    monkeypatch.setattr(Engine, "enabled_strategies", lambda self: [strat])
    store.set("lots_paper", 2)
    asyncio.run(_run_day(engine, fake, day))
    trades = store.trades("paper")
    assert trades, "\n".join(msgs)
    assert not engine.positions
    assert any("BUY" in m for m in msgs) and any("EXIT" in m for m in msgs)
    assert any("PARTIAL" in m for m in msgs)  # 50% booking at target with 2 lots
    assert engine.risk.paper_balance() == pytest.approx(50000 + sum(t["net_pnl"] for t in trades))
    assert any("Daily summary" in m for m in msgs)


def test_engine_full_strategy_set_runs_whole_days(cfg):
    """Run the real 20 strategies over several synthetic days (incl. an expiry day) without errors."""
    for seed, exp_offset in ((11, 1), (12, 0), (13, 1)):
        df = synthetic_candles(7, seed=seed, drift=0.0004 if seed % 2 else -0.0004)
        day = sorted(set(df.index.date))[-1]
        fake = FakeKite(df, expiry=day + timedelta(days=exp_offset))
        store = Store(cfg.db_path + str(seed))
        engine = Engine(cfg, store, fake)
        msgs: list[str] = []

        async def notify(text):
            msgs.append(text)
        engine.notify = notify
        asyncio.run(_run_day(engine, fake, day, step_s=60))
        errors = [m for m in msgs if "error" in m.lower()]
        assert not errors, errors
        assert not engine.positions  # everything squared off by EOD


def test_selection_overrides(cfg):
    from sxpro.strategies import STRATEGY_MAP, apply_selection_overrides
    apply_selection_overrides(cfg)
    apply_selection_overrides(cfg)  # idempotent
    mom, wma, zero = STRATEGY_MAP["SENSEX_MOM_01"], STRATEGY_MAP["SENSEX_WMA_13"], STRATEGY_MAP["SENSEX_0DTE_12"]
    assert (mom.prem_min, mom.prem_max, mom.delta_min, mom.delta_max) == (200, 900, 0.35, 0.75)
    assert wma.delta_max == pytest.approx(0.80) and wma.delta_target == 0.60
    assert zero.prem_max == 250 and zero.delta_min == pytest.approx(0.25)
    # ATM (Δ0.50) at ₹650 used to be rejected (cap ₹400); now it is selectable
    exp = date(2026, 11, 12)
    atm = StrikeCandidate("ATM", 1, 77300, "CE", exp, 20, 0.05, 650, 649, 651, 0.50)
    pick, _ = select_strike([atm], mom.delta_min, mom.delta_max, mom.delta_target, mom.prem_min, mom.prem_max,
                            900, 0.01)
    assert pick is atm


# ---------------------------------------------------------------- charges & report
def test_formula_charges():
    from sxpro.charges import OrderLeg, formula_charges
    buy = formula_charges(OrderLeg("1", "S", "BUY", 80, 588.3))
    sell = formula_charges(OrderLeg("2", "S", "SELL", 80, 525.0))
    # buy: 20 + txn 15.296 + sebi 0.047 + stamp 1.412 + gst 6.362
    assert buy == pytest.approx(43.12, abs=0.01)
    # sell: 20 + STT 42 + txn 13.65 + sebi 0.042 + gst 6.065
    assert sell == pytest.approx(81.76, abs=0.01)


class _FakeKC:
    def __init__(self, orders):
        self._orders = orders

    def orders(self):
        return self._orders

    def get_virtual_contract_note(self, params):
        return [{"charges": {"total": 50.0 if p["transaction_type"] == "SELL" else 30.0}} for p in params]


def _reporter(cfg, kite):
    from sxpro.report import DailyReporter
    from sxpro.sheets import SheetLogger
    store = Store(cfg.db_path)
    return DailyReporter(cfg, kite, store, RiskManager(cfg, store), SheetLogger("", "")), store


def test_live_rows_use_zerodha_charges_and_pnl(cfg):
    day = date(2026, 11, 4)
    ts = datetime(2026, 11, 4, 10, 5, tzinfo=IST)
    mk = lambda oid, side, q, px, tag: {"order_id": oid, "status": "COMPLETE", "exchange": "BFO",
                                         "tradingsymbol": "SENSEX26N0577300CE", "transaction_type": side,
                                         "filled_quantity": q, "average_price": px, "product": "MIS",
                                         "order_type": "LIMIT", "variety": "regular", "tag": tag,
                                         "exchange_timestamp": ts}
    fake = FakeKite(synthetic_candles(3), day)
    fake.kite = _FakeKC([mk("a", "BUY", 40, 300, "sxpro"), mk("b", "SELL", 40, 330, "sxpro")])
    fake.orders = fake.kite.orders
    fake.positions = lambda: {"day": [{"tradingsymbol": "SENSEX26N0577300CE", "pnl": 1200.0}]}
    rep, store = _reporter(cfg, fake)
    store.record_trade({"position_id": "p", "mode": "live", "strategy": "X", "symbol": "SENSEX26N0577300CE",
                        "option_type": "CE", "qty": 40, "entry_price": 300, "exit_price": 330, "gross_pnl": 1200,
                        "charges": 70, "net_pnl": 1130, "entry_time": ts.isoformat(), "exit_time": ts.isoformat(),
                        "exit_reason": "t", "trade_day": day.isoformat()})
    rows = rep.live_rows(day)
    assert len(rows) == 1 and rows[0]["who"] == "Bot" and rows[0]["cost"] == 80 and rows[0]["net"] == 1120
    assert rows[0]["cost_source"] == "zerodha" and rows[0]["pnl_source"] == "zerodha"
    t = store.trades("live")[0]
    assert t["charges"] == 80 and t["net_pnl"] == 1120 and t["cost_source"] == "zerodha"


def test_paper_rows_recompute_and_merge(cfg):
    day = date(2026, 11, 4)
    fake = FakeKite(synthetic_candles(3), day)
    fake.kite = None  # forces formula fallback
    rep, store = _reporter(cfg, fake)
    rep.risk.set_paper_capital(40000)
    t0 = datetime(2026, 11, 4, 10, 0, tzinfo=IST).isoformat()
    store.record_trade({"position_id": "p", "mode": "paper", "strategy": "SENSEX_MOM_01", "symbol": "S1CE",
                        "option_type": "CE", "qty": 40, "entry_price": 300, "exit_price": 330, "gross_pnl": 1200,
                        "charges": 100, "net_pnl": 1100, "entry_time": t0, "exit_time": t0, "exit_reason": "target",
                        "trade_day": day.isoformat(), "legs": [[320, 20], [340, 20]]})
    rep.risk.on_trade_closed("paper", 1100)
    rows = rep.paper_rows(day)
    from sxpro.charges import OrderLeg, formula_charges
    exp = formula_charges(OrderLeg("b", "S1CE", "BUY", 40, 300)) + formula_charges(OrderLeg("s", "S1CE", "SELL", 20, 320)) \
        + formula_charges(OrderLeg("s", "S1CE", "SELL", 20, 340))
    assert rows[0]["cost"] == pytest.approx(exp, abs=0.02)
    assert rep.risk.paper_balance() == pytest.approx(40000 + 1200 - exp, abs=0.02)
    rep.paper_rows(day)  # idempotent
    assert rep.risk.paper_balance() == pytest.approx(40000 + 1200 - exp, abs=0.02)


def test_sheet_trades_logged_once(cfg):
    day = date(2026, 11, 4)
    fake = FakeKite(synthetic_candles(3), day)
    rep, store = _reporter(cfg, fake)
    rep.sheet.enabled = True
    row = {"date": "2026-11-04", "symbol": "S1CE", "who": "Bot", "entry": "10:00", "exit": "10:30", "bought": 40,
           "buy_avg": 1, "sold": 40, "sell_avg": 2, "open_qty": 0, "gross": 40, "cost": 5, "net": 35,
           "cost_source": "zerodha"}
    still_open = {**row, "symbol": "S2CE", "open_qty": 20, "sold": 20}
    rep._sheet_trades([row, still_open], [])
    rep._sheet_trades([row, still_open], [])
    assert len(rep.sheet._queue["Trades"]) == 1
