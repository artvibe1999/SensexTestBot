"""Entry-logic research screener on SENSEX 1-minute data.

usage: python scripts/screen.py DATA_DIR OUT_JSON [--train-end 2025-10-31]

Each candidate rule is simulated day by day on 1-minute bars with decisions at 5-minute
closes (as the bot does), one position at a time, flat by 15:20. Every trade is priced as
an at-the-money weekly option the same way the engine backtest does: Black-Scholes with
India VIX as IV, 0.3% half-spread on entry and exit, Zerodha charges, 2 lots x 20.
Results are split into the train period (rules are chosen here) and the holdout.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from sxpro.charges import OrderLeg, formula_charges
from sxpro.config import IST
from sxpro.options import bs_price, years_to_expiry

LOT, LOTS, STEP, HALF_SPREAD = 20, 2, 100, 0.003
QTY = LOT * LOTS
EXIT_T = time(15, 20)


# ------------------------------------------------------------------ data
def load(d: str):
    rd = lambda f: pd.read_csv(os.path.join(d, f), index_col=0, parse_dates=[0])
    idx1 = rd("idx1.csv.gz")
    idx1.index = idx1.index.tz_convert(IST)
    idx1 = idx1[(idx1.index.time >= time(9, 15)) & (idx1.index.time < time(15, 30))]
    daily = rd("daily.csv.gz")
    daily.index = daily.index.tz_convert(IST)
    vix = rd("vix5.csv.gz")["vix"]
    vix = vix.tz_convert(IST) if vix.index.tz else vix
    vol = None
    if os.path.exists(os.path.join(d, "volproxy5.csv.gz")):
        vol = rd("volproxy5.csv.gz")["value"]
        vol = vol.tz_convert(IST) if vol.index.tz else vol
    days = []
    for day, g in idx1.groupby(idx1.index.date):
        if len(g) < 300:
            continue
        g = g.reindex(pd.date_range(datetime.combine(day, time(9, 15), tzinfo=IST), periods=375, freq="1min")).ffill().bfill()
        days.append((day, g))
    return days, daily, vix, vol


def expiries(days: list[date]) -> list[date]:
    trading = set(days)
    out, d = [], days[0] - timedelta(days=7)
    while d <= days[-1] + timedelta(days=21):
        if d.weekday() == 3:
            e = d
            while e not in trading and e > d - timedelta(days=4) and e <= days[-1]:
                e -= timedelta(days=1)
            out.append(e)
        d += timedelta(days=1)
    return sorted(set(out))


class Pricer:
    def __init__(self, vix: pd.Series, exps: list[date]):
        self.vix, self.exps = vix, exps

    def iv(self, ts) -> float:
        pos = self.vix.index.searchsorted(ts - pd.Timedelta(minutes=5), side="right") - 1
        return max(0.05, float(self.vix.iloc[max(pos, 0)]) / 100)

    def expiry(self, day: date) -> date:
        fut = [e for e in self.exps if e >= day]
        return fut[1] if fut[0] == day else fut[0]   # weekly rule: roll on expiry day

    def trade(self, d: int, t_in, s_in: float, t_out, s_out: float) -> tuple[float, float]:
        """Net P&L (rupees) and premium paid for an ATM option bought at t_in, sold at t_out."""
        exp = self.expiry(t_in.date())
        k = round(s_in / STEP) * STEP
        call = d > 0
        iv = self.iv(t_in)
        p_in = max(0.05, bs_price(s_in, k, years_to_expiry(t_in.to_pydatetime(), exp), 0.065, iv, call))
        p_out = max(0.05, bs_price(s_out, k, years_to_expiry(t_out.to_pydatetime(), exp), 0.065, self.iv(t_out), call))
        buy, sell = p_in * (1 + HALF_SPREAD), p_out * (1 - HALF_SPREAD)
        ch = formula_charges(OrderLeg("b", "X", "BUY", QTY, buy)) + formula_charges(OrderLeg("s", "X", "SELL", QTY, sell))
        return (sell - buy) * QTY - ch, buy


# ------------------------------------------------------------------ per-day features
def day_frames(days, daily, vol):
    """Precompute per day: o,h,l,c arrays (375), session VWAP (proxy volume) and helpers."""
    dclose = daily["close"]
    dclose.index = [ts.date() for ts in dclose.index]
    dhigh = daily["high"]; dhigh.index = dclose.index
    dlow = daily["low"]; dlow.index = dclose.index
    out = []
    for day, g in days:
        prev = dclose[dclose.index < day]
        if prev.empty:
            continue
        pc, ph, pl = float(prev.iloc[-1]), float(dhigh[dhigh.index < day].iloc[-1]), float(dlow[dlow.index < day].iloc[-1])
        o, h, l, c = (g[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        tp = (h + l + c) / 3
        if vol is not None:
            v5 = vol.reindex(g.index.floor("5min")).fillna(0).to_numpy(float) / 5
        else:
            v5 = np.zeros(375)
        cv = np.cumsum(v5)
        vwap = np.where(cv > 0, np.cumsum(tp * v5) / np.where(cv > 0, cv, 1), np.cumsum(tp) / np.arange(1, 376))
        tr = np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])
        out.append({"day": day, "idx": g.index, "o": o, "h": h, "l": l, "c": c, "vwap": vwap,
                    "pc": pc, "ph": ph, "pl": pl, "open": o[0], "prev_range": ph - pl,
                    "atr1": float(np.mean(tr[:30])) if len(tr) else 1.0})
    # noise: |close/open - 1| per minute of day, for rolling sigma
    move = np.array([np.abs(f["c"] / f["open"] - 1) for f in out])
    return out, move


def minute(t: time) -> int:
    return (t.hour - 9) * 60 + t.minute - 15


# ------------------------------------------------------------------ simulation
def simulate(frames, move, pricer, rule, p):
    """Return list of trades (day, dir, entry ts, exit ts, net, premium, reason)."""
    trades = []
    last_entry = minute(p.get("last_entry", time(14, 45)))
    exit_m = minute(EXIT_T)
    for i, f in enumerate(frames):
        c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
        sig = rule(i, f, frames, move, p)        # list of (minute, dir, stop, target or None)
        if not sig:
            continue
        busy_until = -1
        for m_in, d, stop, target in sig:
            if m_in <= busy_until or m_in > last_entry:
                continue
            s_in = c[m_in]
            best = s_in
            m_out, reason = exit_m, "eod"
            for m in range(m_in + 1, exit_m + 1):
                if stop is not None and ((d > 0 and l[m] <= stop) or (d < 0 and h[m] >= stop)):
                    m_out, reason, s_out = m, "stop", stop
                    break
                if target is not None and ((d > 0 and h[m] >= target) or (d < 0 and l[m] <= target)):
                    m_out, reason, s_out = m, "target", target
                    break
                best = max(best, h[m]) if d > 0 else min(best, l[m])
                if (m + 1) % 5 == 0:   # 5-minute close
                    ex = p.get("exit", "eod")
                    if ex == "vwap" and d * (c[m] - vw[m]) < 0:
                        m_out, reason = m, "vwap"; break
                    if ex == "trail" and d * (c[m] - (best - d * p.get("trail_atr", 3.0) * f["atr1"] * 5 ** 0.5)) < 0:
                        m_out, reason = m, "trail"; break
                    if ex == "noise" and p.get("_bound") is not None:
                        ub, lb = p["_bound"](i, m)
                        lvl = max(ub, vw[m]) if d > 0 else min(lb, vw[m])
                        if d * (c[m] - lvl) < 0:
                            m_out, reason = m, "noise"; break
            else:
                pass
            if reason in ("eod", "vwap", "trail", "noise"):
                s_out = c[m_out]
            net, prem = pricer.trade(d, f["idx"][m_in], s_in, f["idx"][m_out], s_out)
            trades.append((f["day"].isoformat(), d, m_in, m_out, round(net, 2), round(prem, 2), reason))
            busy_until = m_out
            if not p.get("multi", False):
                break
    return trades


# ------------------------------------------------------------------ rule families
def at5(m: int) -> bool:
    return (m + 1) % 5 == 0


def r_noise(i, f, frames, move, p):
    L, k, F = p["L"], p["k"], p["F"]
    if i < L:
        return []
    sigma = move[i - L:i].mean(axis=0)
    up_ref, dn_ref = max(f["open"], f["pc"]), min(f["open"], f["pc"])
    ub, lb = up_ref * (1 + k * sigma), dn_ref * (1 - k * sigma)
    p["_bound"] = lambda _i, m: (ub[m], lb[m])
    out = []
    c, vw = f["c"], f["vwap"]
    for m in range(minute(time(9, 45)) - 1, minute(time(14, 45)), F):
        if c[m] > ub[m] and c[m] > vw[m]:
            out.append((m, 1, None, None))
        elif c[m] < lb[m] and c[m] < vw[m]:
            out.append((m, -1, None, None))
    return out


def r_orb_dir(i, f, frames, move, p):
    R = p["R"]
    c, h, l = f["c"], f["h"], f["l"]
    hi, lo = h[:R].max(), l[:R].min()
    first_dir = np.sign(c[R - 1] - f["open"])
    if first_dir == 0:
        return []
    cut = minute(p["cutoff"])
    for m in range(R + 4, cut, 5):
        if first_dir > 0 and c[m] > hi:
            stop = lo if p["stop"] == "opp" else (hi + lo) / 2
            return [(m, 1, stop, c[m] + p["rr"] * (c[m] - stop) if p.get("rr") else None)]
        if first_dir < 0 and c[m] < lo:
            stop = hi if p["stop"] == "opp" else (hi + lo) / 2
            return [(m, -1, stop, c[m] - p["rr"] * (stop - c[m]) if p.get("rr") else None)]
    return []


def r_late_mom(i, f, frames, move, p):
    m = minute(p["at"]) - 1
    c, vw = f["c"], f["vwap"]
    ref = f["pc"] if p["ref"] == "pc" else f["open"]
    ret = c[m] / ref - 1
    if ret > p["thr"] and c[m] > vw[m]:
        return [(m, 1, None, None)]
    if ret < -p["thr"] and c[m] < vw[m]:
        return [(m, -1, None, None)]
    return []


def r_first30(i, f, frames, move, p):
    m30 = minute(time(9, 45)) - 1
    r30 = f["c"][m30] / f["pc"] - 1
    m = minute(p["at"]) - 1
    if abs(r30) < p["thr"]:
        return []
    d = 1 if r30 > 0 else -1
    if p.get("confirm") and d * (f["c"][m] - f["vwap"][m]) < 0:
        return []
    return [(m, d, None, None)]


def r_gap(i, f, frames, move, p):
    gap = f["open"] / f["pc"] - 1
    if abs(gap) < p["g"]:
        return []
    d = 1 if gap > 0 else -1
    R = p["R"]
    c, h, l = f["c"], f["h"], f["l"]
    if d * (c[R - 1] - f["open"]) <= 0:
        return []   # first candle must continue the gap
    stop = l[:R].min() if d > 0 else h[:R].max()
    return [(R - 1, d, stop, None)]


def r_vbo(i, f, frames, move, p):
    k = p["k"]
    up, dn = f["open"] + k * f["prev_range"], f["open"] - k * f["prev_range"]
    c = f["c"]
    for m in range(9, minute(p["cutoff"]), 5):
        if c[m] > up:
            return [(m, 1, f["open"] if p["stop"] == "open" else dn, None)]
        if c[m] < dn:
            return [(m, -1, f["open"] if p["stop"] == "open" else up, None)]
    return []


def r_pdb(i, f, frames, move, p):
    c = f["c"]
    if not (f["pl"] <= f["open"] <= f["ph"]):
        return []   # opens inside yesterday's range
    for m in range(minute(time(9, 30)) - 1, minute(p["cutoff"]), 5):
        if c[m] > f["ph"] and c[m - 5] <= f["ph"]:
            return [(m, 1, f["ph"] - p["buf"] * f["prev_range"], None)]
        if c[m] < f["pl"] and c[m - 5] >= f["pl"]:
            return [(m, -1, f["pl"] + p["buf"] * f["prev_range"], None)]
    return []


FAMILIES = {
    "NOISE": (r_noise, {"L": [10, 14, 20], "k": [1.0, 1.25, 1.5], "F": [15, 30], "exit": ["noise", "vwap", "eod"],
                        "multi": [True]}),
    "ORB_DIR": (r_orb_dir, {"R": [5, 15, 30], "cutoff": [time(11, 0), time(13, 0)], "stop": ["opp", "mid"],
                            "rr": [None, 2.0], "exit": ["eod", "vwap", "trail"]}),
    "LATE_MOM": (r_late_mom, {"at": [time(14, 0), time(14, 30), time(14, 50)], "thr": [0.003, 0.006, 0.01],
                              "ref": ["pc", "open"], "exit": ["eod"]}),
    "FIRST30": (r_first30, {"at": [time(9, 45), time(14, 30), time(14, 50)], "thr": [0.002, 0.005, 0.01],
                            "confirm": [False, True], "exit": ["eod", "vwap"]}),
    "GAP": (r_gap, {"g": [0.003, 0.006, 0.01], "R": [5, 15, 30], "exit": ["eod", "vwap", "trail"]}),
    "VBO": (r_vbo, {"k": [0.2, 0.35, 0.5, 0.7], "cutoff": [time(12, 0), time(14, 0)], "stop": ["open", "opp"],
                    "exit": ["eod", "vwap", "trail"]}),
    "PDB": (r_pdb, {"cutoff": [time(12, 0), time(14, 30)], "buf": [0.1, 0.25], "exit": ["eod", "vwap", "trail"]}),
}


def stats(trades, train_end: date):
    df = pd.DataFrame(trades, columns=["day", "dir", "m_in", "m_out", "net", "prem", "reason"])
    if df.empty:
        return None
    df["year"] = df["day"].str[:4]
    df["train"] = pd.to_datetime(df["day"]).dt.date <= train_end
    out = {}
    for part, g in (("train", df[df.train]), ("holdout", df[~df.train])):
        w, lo = g.net[g.net > 0].sum(), -g.net[g.net <= 0].sum()
        out[part] = {"trades": int(len(g)), "net": round(float(g.net.sum())), "win": round(100 * float((g.net > 0).mean()), 1) if len(g) else 0,
                     "pf": round(float(w / lo), 2) if lo > 0 else None,
                     "dd": round(float((g.net.cumsum().cummax() - g.net.cumsum()).max())) if len(g) else 0,
                     "avg_prem": round(float(g.prem.mean())) if len(g) else 0}
    yr = df[df.train].groupby("year")["net"].sum().round(0)
    out["train_years"] = {k: int(v) for k, v in yr.items()}
    out["holdout_months"] = {k: int(v) for k, v in df[~df.train].groupby(df["day"].str[:7])["net"].sum().round(0).items()}
    out["exits"] = df.reason.value_counts().to_dict()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("out")
    ap.add_argument("--train-end", default="2025-10-31")
    ap.add_argument("--families", default=",".join(FAMILIES))
    a = ap.parse_args()
    days, daily, vix, vol = load(a.data)
    frames, move = day_frames(days, daily, vol)
    pricer = Pricer(vix, expiries([f["day"] for f in frames]))
    te = date.fromisoformat(a.train_end)
    results = []
    for fam in a.families.split(","):
        rule, grid = FAMILIES[fam]
        keys = list(grid)
        for combo in itertools.product(*(grid[k] for k in keys)):
            p = dict(zip(keys, combo))
            tr = simulate(frames, move, pricer, rule, p)
            s = stats(tr, te)
            if s:
                results.append({"family": fam, "params": {k: (v.strftime("%H:%M") if isinstance(v, time) else v) for k, v in p.items()
                                                            if not k.startswith("_")}, **s})
                print(fam, results[-1]["params"], s["train"]["trades"], s["train"]["net"], s["train"]["pf"], "| holdout",
                      s["holdout"]["trades"], s["holdout"]["net"], s["holdout"]["pf"], flush=True)
    json.dump({"days": len(frames), "first": str(frames[0]["day"]), "last": str(frames[-1]["day"]),
               "train_end": a.train_end, "results": results}, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
