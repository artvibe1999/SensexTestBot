"""Historical backtest that replays the *real* trading engine minute by minute.

    python -m sxpro.backtest fetch --days 365        # on the VM (needs a Kite session)
    python -m sxpro.backtest run --data DIR --out results.json [--capital 40000 --lots 2]

What is real vs modelled
* SENSEX 1-minute candles (Kite) drive LTP-based stops/targets; 5-minute candles are
  resampled from them, exactly as the live bot sees closed 5-minute candles.
* The regime engine, all 20 strategies, strike selection, sizing, risk limits, exits,
  partial booking, trailing and charges are the production code paths (Engine).
* Option premiums are modelled: Kite has no history for expired option contracts, so
  each strike is priced with Black-Scholes using India VIX as IV (flat smile), with a
  0.3% half-spread (paper fills at ask / bid).
* Volume: Kite keeps no history for expired SENSEX futures and offers no continuous
  intraday futures series, so the volume proxy is the 5-minute traded value of the
  largest SENSEX constituents (RVOL is a ratio, so only the shape matters).
* Weekly SENSEX expiry = Thursday (previous trading day if Thursday is a holiday).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, time, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import IST, Config
from .kite_service import INDEX_SYMBOL
from .market import MarketContext, classify_regime, resample_15
from .options import bs_price, years_to_expiry

VIX_TOKEN = 264969
CONSTITUENTS = ["HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "BHARTIARTL", "LT", "ITC", "TCS", "AXISBANK",
                "KOTAKBANK", "SBIN", "M&M", "BAJFINANCE", "HINDUNILVR", "SUNPHARMA"]
LOT = 20
STEP = 100
HALF_SPREAD = 0.003


# ============================================================ fetch (runs on the VM)
def _hist(kc, token: int, start: datetime, end: datetime, interval: str, chunk_days: int) -> pd.DataFrame:
    import time as _t
    out, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=chunk_days), end)
        rows = kc.historical_data(token, cur, nxt, interval)
        out.extend(rows)
        cur = nxt + timedelta(seconds=1)
        _t.sleep(0.4)
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out).drop_duplicates("date")
    df["date"] = pd.to_datetime(df["date"]).dt.tz_convert(IST)
    return df.set_index("date").sort_index()


def fetch(days: int, out_dir: str) -> None:
    from .kite_service import KiteService
    k = KiteService(Config())
    if not k.load_saved_token():
        raise SystemExit("Kite not logged in")
    kc = k.kite
    os.makedirs(out_dir, exist_ok=True)
    end = datetime.now(IST).replace(hour=15, minute=31, second=0, microsecond=0)
    if datetime.now(IST).time() < time(15, 31):
        end -= timedelta(days=1)
    start = (end - timedelta(days=days)).replace(hour=9, minute=0)

    idx1 = _hist(kc, 265, start, end, "minute", 55)
    idx1[["open", "high", "low", "close"]].to_csv(os.path.join(out_dir, "idx1.csv.gz"))
    print("index 1m", len(idx1), idx1.index[0], idx1.index[-1])

    daily = _hist(kc, 265, start - timedelta(days=120), end, "day", 1500)
    daily[["open", "high", "low", "close"]].to_csv(os.path.join(out_dir, "daily.csv.gz"))

    vix = _hist(kc, VIX_TOKEN, start, end, "5minute", 95)
    vix[["close"]].rename(columns={"close": "vix"}).to_csv(os.path.join(out_dir, "vix5.csv.gz"))
    print("vix 5m", len(vix))

    nse = {r["tradingsymbol"]: r["instrument_token"] for r in kc.instruments("NSE") if r["segment"] == "NSE"}
    value = None
    for sym in CONSTITUENTS:
        df = _hist(kc, nse[sym], start, end, "5minute", 95)
        v = (df["volume"] * df["close"]).rename(sym)
        value = v.to_frame() if value is None else value.join(v, how="outer")
        print("constituent", sym, len(df))
    value.fillna(0).sum(axis=1).rename("value").to_csv(os.path.join(out_dir, "volproxy5.csv.gz"))

    # proxy validation: real SENSEX futures volume (recent, liquid period only)
    k.refresh_instruments()
    fut = _hist(kc, int(k.futures[0]["instrument_token"]), end - timedelta(days=30), end, "5minute", 30)
    fut[["volume"]].to_csv(os.path.join(out_dir, "sxfut5.csv.gz"))
    print("done ->", out_dir)


# ============================================================ market data for the replay
class Data:
    def __init__(self, d: str):
        rd = lambda f: pd.read_csv(os.path.join(d, f), index_col=0, parse_dates=[0])
        self.idx1 = rd("idx1.csv.gz")
        self.idx1.index = self.idx1.index.tz_convert(IST)
        self.daily = rd("daily.csv.gz")
        self.daily.index = self.daily.index.tz_convert(IST)
        vix = rd("vix5.csv.gz")["vix"]
        self.vix = vix.tz_convert(IST) if vix.index.tz else vix
        vol = rd("volproxy5.csv.gz")["value"]
        self.vol = vol.tz_convert(IST) if vol.index.tz else vol
        self.fut = None
        if os.path.exists(os.path.join(d, "sxfut5.csv.gz")):
            f = rd("sxfut5.csv.gz")["volume"]
            self.fut = f.tz_convert(IST) if f.index.tz else f

        agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
        five = self.idx1.resample("5min", origin="start_day", offset="15min").agg(agg).dropna()
        five = five[(five.index.time >= time(9, 15)) & (five.index.time < time(15, 30))]
        five["volume"] = self.vol.reindex(five.index).fillna(0.0)
        self.idx5 = five
        self.enriched = ind.enrich(five)
        self.end5 = (five.index + pd.Timedelta(minutes=5)).values
        f15 = resample_15(five)
        self.enr15 = ind.enrich(f15)
        self.end15 = (f15.index + pd.Timedelta(minutes=15)).values
        self.close1 = self.idx1["close"]
        self.days = sorted({ts.date() for ts in self.idx5.index})
        dd = self.daily.copy()
        self.daily_adx = ind.adx(dd, 14)["adx"]
        self.expiries = self._expiries()

    def _expiries(self) -> list[date]:
        trading = set(self.days)
        out, d = [], self.days[0] - timedelta(days=7)
        last = self.days[-1] + timedelta(days=60)
        while d <= last:
            if d.weekday() == 3:
                e = d
                if d <= self.days[-1]:
                    while e not in trading and e > d - timedelta(days=4):
                        e -= timedelta(days=1)
                out.append(e)
            d += timedelta(days=1)
        return out

    def rvol_proxy_check(self) -> Optional[float]:
        if self.fut is None or self.fut.empty:
            return None
        j = pd.concat([self.vol, self.fut], axis=1, keys=["proxy", "fut"]).dropna()
        j = j[j["fut"] > 0]
        r = j / j.shift(1).rolling(20, min_periods=5).mean()
        return float(r.corr().iloc[0, 1])


class HistKite:
    """Implements the KiteService surface the Engine uses, from historical data."""

    def __init__(self, data: Data):
        self.d = data
        self.ready = True
        self.user = {"user_id": "BACKTEST"}
        self.now: datetime = datetime.now(IST)
        self.options: list = []
        self.futures: list = []

    def load_saved_token(self):
        return True

    def refresh_instruments(self, force: bool = False):
        return None

    def login_url(self):
        return ""

    def lot_size(self):
        return LOT

    def expiries(self):
        today = self.now.date()
        return [e for e in self.d.expiries if e >= today][:4]

    def _spot(self) -> float:
        pos = self.d.close1.index.searchsorted(pd.Timestamp(self.now) - pd.Timedelta(minutes=1), side="right") - 1
        return float(self.d.close1.iloc[max(pos, 0)])

    def spot(self):
        return self._spot()

    def _iv(self) -> float:
        v = self.d.vix
        pos = v.index.searchsorted(pd.Timestamp(self.now) - pd.Timedelta(minutes=5), side="right") - 1
        return max(0.05, float(v.iloc[max(pos, 0)]) / 100.0)

    def chain(self, expiry, spot, width=10):
        atm = round(spot / STEP) * STEP
        rows = []
        for k in range(-width, width + 1):
            strike = atm + k * STEP
            for ot in ("CE", "PE"):
                rows.append({"tradingsymbol": f"SX|{expiry.isoformat()}|{int(strike)}|{ot}",
                             "instrument_token": hash((expiry, strike, ot)) & 0xFFFFFFF, "strike": float(strike),
                             "instrument_type": ot, "expiry": expiry, "lot_size": LOT, "tick_size": 0.05})
        return rows

    def quote(self, keys):
        spot, iv, out = self._spot(), self._iv(), {}
        for key in keys:
            if key == INDEX_SYMBOL:
                out[key] = {"last_price": spot}
                continue
            _, exp, strike, ot = key.split(":", 1)[1].split("|")
            t = years_to_expiry(self.now, date.fromisoformat(exp))
            px = max(0.05, bs_price(spot, float(strike), t, 0.065, iv, ot == "CE"))
            half = max(0.05, round(px * HALF_SPREAD / 0.05) * 0.05)
            out[key] = {"last_price": round(px, 2),
                        "depth": {"buy": [{"price": round(max(0.05, px - half), 2), "quantity": 1000}],
                                  "sell": [{"price": round(px + half, 2), "quantity": 1000}]}}
        return out

    def funds(self):
        return {"net": 0.0, "available": 0.0, "utilised": 0.0}

    def daily_candles(self, now, days=60):
        return self.d.daily[self.d.daily.index < pd.Timestamp(now)]

    def index_candles(self, now, interval="5minute", days=8):
        if interval == "3minute":
            day = self.d.idx1[self.d.idx1.index.date == now.date()]
            day = day[day.index + pd.Timedelta(minutes=1) <= pd.Timestamp(now)]
            agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
            out = day.resample("3min", origin="start_day", offset="15min").agg(agg).dropna()
            out["volume"] = 0.0
            return out[out.index + pd.Timedelta(minutes=3) <= pd.Timestamp(now)]
        raise NotImplementedError


def _make_engine(data: Data, enabled: Optional[str], capital: float, lots, tmpdir: str):
    os.environ["DATA_DIR"] = tmpdir
    os.environ["PAPER_CAPITAL"] = str(capital)
    for k in ("SHEETS_WEBHOOK_URL", "SHEETS_SECRET", "REPORT_GCS_BUCKET"):
        os.environ.pop(k, None)
    from .engine import Engine
    from .store import Store
    from .strategies import ALL_STRATEGIES

    cfg = Config()
    store = Store(cfg.db_path)
    kite = HistKite(data)

    class BTEngine(Engine):
        async def build_ctx(self, now):
            i = int(np.searchsorted(data.end5, np.datetime64(pd.Timestamp(now).tz_convert("UTC").tz_localize(None)), side="right")) - 1
            if i < 0:
                return None
            df = data.enriched.iloc[max(0, i - 599): i + 1]
            if df.index[-1].date() != now.date():
                return None
            j = int(np.searchsorted(data.end15, np.datetime64(pd.Timestamp(now).tz_convert("UTC").tz_localize(None)), side="right"))
            df15 = data.enr15.iloc[max(0, j - 200): j] if j >= 30 else None
            prev = data.daily[data.daily.index.date < now.date()]
            p = prev.iloc[-1]
            adx_v = float(data.daily_adx.loc[prev.index[-1]]) if len(prev) > 20 else float("nan")
            exps = kite.expiries()
            ctx = MarketContext(df=df, now=now, prev_day={"open": p.open, "high": p.high, "low": p.low, "close": p.close},
                                daily_adx=adx_v, nearest_expiry=exps[0] if exps else None, df15=df15)
            ctx.regime, ctx.regime_detail = classify_regime(ctx)
            return ctx

    eng = BTEngine(cfg, store, kite)
    eng.clock = lambda: kite.now
    store.set("lots_paper", lots)
    store.set("mode", "paper")
    if enabled:
        store.set("disabled", [s.sid for s in ALL_STRATEGIES if s.sid != enabled])
    skips: dict[str, int] = {}

    async def notify(text: str):
        if text.startswith("⏭️"):
            why = text.split("skipped:", 1)[-1].strip().split("(")[0].strip()
            skips[why] = skips.get(why, 0) + 1
    eng.notify = notify
    return eng, store, kite, skips


def run_one(args: tuple) -> dict:
    data_dir, enabled, capital, lots = args
    data = Data(data_dir)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        eng, store, kite, skips = _make_engine(data, enabled, capital, lots, tmp)

        async def go():
            for day in data.days:
                t = datetime.combine(day, time(9, 16, 5), tzinfo=IST)
                end = datetime.combine(day, time(15, 30, 5), tzinfo=IST)
                while t <= end:
                    kite.now = t
                    await eng.tick(t)
                    t += timedelta(minutes=1)
        asyncio.run(go())
        trades = store.trades("paper")
        return {"strategy": enabled or "ALL (bot rules)", "trades": trades, "skips": skips,
                "final_balance": eng.risk.paper_balance(), "capital": capital, "lots": lots,
                "start": str(data.days[0]), "end": str(data.days[-1]), "sessions": len(data.days)}


# ============================================================ metrics
def metrics(res: dict) -> dict:
    t = res["trades"]
    nets = [x["net_pnl"] for x in t]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    eq = np.cumsum(nets) if nets else np.array([0.0])
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])))
    hold = [(datetime.fromisoformat(x["exit_time"]) - datetime.fromisoformat(x["entry_time"])).total_seconds() / 60
            for x in t]
    reasons: dict[str, int] = {}
    for x in t:
        r = x["exit_reason"].split("(")[0].split(" SENSEX")[0].strip()
        reasons[r] = reasons.get(r, 0) + 1
    return {
        "strategy": res["strategy"], "trades": len(t), "wins": len(wins),
        "win_rate": round(100 * len(wins) / len(t), 1) if t else 0.0,
        "gross": round(sum(x["gross_pnl"] for x in t), 2), "charges": round(sum(x["charges"] for x in t), 2),
        "net": round(sum(nets), 2), "avg_win": round(np.mean(wins), 2) if wins else 0.0,
        "avg_loss": round(np.mean(losses), 2) if losses else 0.0,
        "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
        "expectancy": round(np.mean(nets), 2) if nets else 0.0, "max_drawdown": round(dd, 2),
        "best": round(max(nets), 2) if nets else 0.0, "worst": round(min(nets), 2) if nets else 0.0,
        "avg_hold_min": round(float(np.mean(hold)), 1) if hold else 0.0,
        "return_pct": round(100 * sum(nets) / res["capital"], 1), "exit_reasons": reasons,
        "skips": res["skips"], "final_balance": round(res["final_balance"], 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--days", type=int, default=365)
    f.add_argument("--out", default=os.path.join(Config().data_dir, "backtest"))
    r = sub.add_parser("run")
    r.add_argument("--data", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--capital", type=float, default=40000)
    r.add_argument("--lots", default="2")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.days, a.out)
        return
    from .strategies import ALL_STRATEGIES
    lots = a.lots if a.lots == "auto" else int(a.lots)
    jobs = [(a.data, None, a.capital, lots)] + [(a.data, s.sid, a.capital, lots) for s in ALL_STRATEGIES]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(run_one, jobs))
    data = Data(a.data)
    out = {"period": {"start": results[0]["start"], "end": results[0]["end"], "sessions": results[0]["sessions"]},
           "capital": a.capital, "lots": lots, "rvol_proxy_corr": data.rvol_proxy_check(),
           "summary": [metrics(x) for x in results], "trades": {x["strategy"]: x["trades"] for x in results}}
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    for m in out["summary"]:
        print(f"{m['strategy']:18s} n={m['trades']:4d} win={m['win_rate']:5.1f}% net={m['net']:>11,.0f} "
              f"pf={m['profit_factor']} dd={m['max_drawdown']:,.0f}")


if __name__ == "__main__":
    main()
