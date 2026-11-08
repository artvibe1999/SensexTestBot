"""Third screen + portfolio simulator.

usage:
  python scripts/screen3.py DATA OUT_JSON screen [--families ...]
  python scripts/screen3.py DATA OUT_JSON portfolio SPEC_JSON
SPEC_JSON: {"sets": {"name": [[family, params], ...priority order]}}
The portfolio mode replays the bot's rules on the same simulator: one position at a time,
at most 3 trades a day, signals taken in priority order, each trade exits by its own rule.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import screen as S  # noqa: E402
import screen2 as S2  # noqa: E402
from screen import minute  # noqa: E402


def r_thrust(i, f, frames, move, p):
    """Thrust bar: a 5-min candle with range > m x ATR closing in its outer 20%, beyond the
    noise band on the VWAP side -> follow; stop at the bar's other end."""
    b = S2.sigma_bands(i, f, move, 14, p["k"])
    if b is None:
        return []
    ub, lb = b
    c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
    atr = f["atr1"] * 5 ** 0.5
    for m in range(minute(time(9, 45)) - 1, minute(time(14, 30)), 5):
        hi, lo = h[m - 4:m + 1].max(), l[m - 4:m + 1].min()
        if hi - lo < p["m"] * atr:
            continue
        pos = (c[m] - lo) / (hi - lo)
        if pos >= 0.8 and c[m] > ub[m] and c[m] > vw[m]:
            return [(m, 1, lo, None)]
        if pos <= 0.2 and c[m] < lb[m] and c[m] < vw[m]:
            return [(m, -1, hi, None)]
    return []


def r_lunch_brk(i, f, frames, move, p):
    """Break of the 12:00-13:00 range after 13:00, in the direction of the day (vs open)."""
    c, h, l = f["c"], f["h"], f["l"]
    a, b = minute(time(12, 0)), minute(time(13, 0))
    hi, lo = h[a:b].max(), l[a:b].min()
    day = np.sign(c[b - 1] - f["open"])
    if abs(c[b - 1] / f["open"] - 1) < p["min_move"]:
        return []
    for m in range(b + 4, minute(p["cutoff"]), 5):
        if day > 0 and c[m] > hi:
            return [(m, 1, lo, None)]
        if day < 0 and c[m] < lo:
            return [(m, -1, hi, None)]
    return []


def r_orb60(i, f, frames, move, p):
    """60-minute opening range breakout either side, by cutoff; stop mid/opposite."""
    c, h, l = f["c"], f["h"], f["l"]
    hi, lo = h[:60].max(), l[:60].min()
    for m in range(64, minute(p["cutoff"]), 5):
        if c[m] > hi:
            return [(m, 1, lo if p["stop"] == "opp" else (hi + lo) / 2, None)]
        if c[m] < lo:
            return [(m, -1, hi if p["stop"] == "opp" else (hi + lo) / 2, None)]
    return []


def r_week_brk(i, f, frames, move, p):
    """Break of the prior N-day high/low (after 09:30, by cutoff), VWAP side."""
    N = p["N"]
    if i < N:
        return []
    hi = max(frames[j]["h"].max() for j in range(i - N, i))
    lo = min(frames[j]["l"].min() for j in range(i - N, i))
    if not (lo < f["open"] < hi):
        return []
    c, vw = f["c"], f["vwap"]
    for m in range(minute(time(9, 30)) - 1, minute(p["cutoff"]), 5):
        if c[m] > hi and c[m] > vw[m]:
            return [(m, 1, f["ph"] if f["ph"] < c[m] else vw[m], None)]
        if c[m] < lo and c[m] < vw[m]:
            return [(m, -1, f["pl"] if f["pl"] > c[m] else vw[m], None)]
    return []


def r_close_strength(i, f, frames, move, p):
    """Yesterday closed in its top/bottom 20% and today holds beyond yesterday's close at
    `at` on the VWAP side -> continuation."""
    y = frames[i - 1] if i else None
    if y is None:
        return []
    yh, yl = y["h"].max(), y["l"].min()
    if yh - yl <= 0:
        return []
    pos = (y["c"][-1] - yl) / (yh - yl)
    m = minute(p["at"]) - 1
    c, vw = f["c"], f["vwap"]
    if pos >= 0.8 and c[m] > f["pc"] * (1 + p["buf"]) and c[m] > vw[m]:
        return [(m, 1, min(f["l"][:m + 1].min(), f["pc"]), None)]
    if pos <= 0.2 and c[m] < f["pc"] * (1 - p["buf"]) and c[m] < vw[m]:
        return [(m, -1, max(f["h"][:m + 1].max(), f["pc"]), None)]
    return []


T = lambda *a: [time(*x) for x in a]
FAMILIES = {
    "THRUST": (r_thrust, {"m": [1.5, 2.0, 2.5], "k": [0.5, 0.75, 1.0], "exit": ["eod", "trail", "vwap"]}),
    "LUNCH_BRK": (r_lunch_brk, {"min_move": [0.0, 0.003, 0.006], "cutoff": T((14, 0), (14, 45)), "exit": ["eod", "trail"]}),
    "ORB60": (r_orb60, {"cutoff": T((12, 0), (13, 30)), "stop": ["opp", "mid"], "exit": ["eod", "trail", "vwap"]}),
    "WEEK_BRK": (r_week_brk, {"N": [3, 5, 10], "cutoff": T((12, 0), (14, 0)), "exit": ["eod", "trail", "vwap"]}),
    "CLOSE_STR": (r_close_strength, {"at": T((9, 45), (10, 30), (11, 30)), "buf": [0.0, 0.002, 0.004], "exit": ["eod", "trail"]}),
}
ALL = {**S.FAMILIES, **S2.FAMILIES, **FAMILIES}

# ------------------------------------------------------------------ portfolio replay
CTX: dict = {}


def init(data):
    days, daily, vix, vol = S.load(data)
    frames, move = S.day_frames(days, daily, vol)
    CTX.update(frames=frames, move=move, pricer=S.Pricer(vix, S.expiries([f["day"] for f in frames])))


def exit_trade(f, i, m_in, d, stop, target, p, move):
    c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
    exit_m = minute(S.EXIT_T)
    best = c[m_in]
    for m in range(m_in + 1, exit_m + 1):
        if stop is not None and ((d > 0 and l[m] <= stop) or (d < 0 and h[m] >= stop)):
            return m, stop, "stop"
        if target is not None and ((d > 0 and h[m] >= target) or (d < 0 and l[m] <= target)):
            return m, target, "target"
        best = max(best, h[m]) if d > 0 else min(best, l[m])
        if (m + 1) % 5 == 0:
            ex = p.get("exit", "eod")
            if ex == "vwap" and d * (c[m] - vw[m]) < 0:
                return m, c[m], "vwap"
            if ex == "trail" and d * (c[m] - (best - d * p.get("trail_atr", 3.0) * f["atr1"] * 5 ** 0.5)) < 0:
                return m, c[m], "trail"
            if ex == "noise" and p.get("_bound") is not None:
                ub, lb = p["_bound"](i, m)
                lvl = max(ub, vw[m]) if d > 0 else min(lb, vw[m])
                if d * (c[m] - lvl) < 0:
                    return m, c[m], "noise"
    return exit_m, c[exit_m], "eod"


def portfolio(members, max_trades=3):
    frames, move, pricer = CTX["frames"], CTX["move"], CTX["pricer"]
    trades = []
    for i, f in enumerate(frames):
        sigs = []   # (minute, priority, dir, stop, target, params, name)
        for pr, mem in enumerate(members):
            name, fam, p = mem if len(mem) == 3 else (mem[0], mem[0], mem[1])
            p = dict(p)
            for k, v in list(p.items()):
                if isinstance(v, str) and len(v) == 5 and v[2] == ":":
                    p[k] = time.fromisoformat(v)
            for m, d, stop, target in ALL[fam][0](i, f, frames, move, p) or []:
                if m <= minute(p.get("last_entry", time(14, 45))):
                    sigs.append((m, pr, d, stop, target, p, name))
        sigs.sort(key=lambda s: (s[0], s[1]))
        busy, n = -1, 0
        for m, pr, d, stop, target, p, fam in sigs:
            if m <= busy or n >= max_trades:
                continue
            m_out, s_out, why = exit_trade(f, i, m, d, stop, target, p, move)
            net, prem = pricer.trade(d, f["idx"][m], f["c"][m], f["idx"][m_out], s_out)
            trades.append((f["day"].isoformat(), d, m, m_out, round(net, 2), round(prem, 2), fam))
            busy, n = m_out, n + 1
    return trades


def summarize(trades):
    s = S.stats(trades, date(2025, 10, 31))
    nets = [t[4] for t in trades]
    years: dict = {}
    for t in trades:
        years[t[0][:4]] = years.get(t[0][:4], 0) + t[4]
    s["years"] = {k: round(v) for k, v in sorted(years.items())}
    s["by_member"] = {}
    for t in trades:
        s["by_member"].setdefault(t[6], [0, 0.0])
        s["by_member"][t[6]][0] += 1; s["by_member"][t[6]][1] += t[4]
    s["by_member"] = {k: [v[0], round(v[1])] for k, v in s["by_member"].items()}
    s["all_net"] = round(sum(nets))
    return s


def run_screen(job):
    fam, p = job
    tr = S.simulate(CTX["frames"], CTX["move"], CTX["pricer"], ALL[fam][0], dict(p))
    s = S.stats(tr, date(2025, 10, 31))
    if not s:
        return None
    return {"family": fam, "params": {k: (v.strftime("%H:%M") if isinstance(v, time) else v) for k, v in p.items()}, **s}


def run_set(job):
    name, members = job
    return name, summarize(portfolio(members))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("out"); ap.add_argument("mode")
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--workers", type=int, default=9)
    a = ap.parse_args()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=init, initargs=(a.data,)) as ex:
        if a.mode == "screen":
            jobs = []
            for fam in a.families.split(","):
                grid = ALL[fam][1]
                keys = list(grid)
                jobs += [(fam, dict(zip(keys, combo))) for combo in itertools.product(*(grid[k] for k in keys))]
            res = [r for r in ex.map(run_screen, jobs, chunksize=2) if r]
            for r in res:
                print(r["family"], r["params"], r["train"]["trades"], r["train"]["net"], r["train"]["pf"], "| holdout",
                      r["holdout"]["trades"], r["holdout"]["net"], r["holdout"]["pf"], flush=True)
            json.dump({"results": res}, open(a.out, "w"), indent=1, default=str)
        else:
            sets = json.load(open(a.spec))["sets"]
            out = {}
            for name, s in ex.map(run_set, list(sets.items())):
                out[name] = s
                print(name, "| all", s["all_net"], "| train", s["train"]["net"], s["train"]["pf"], s["train"]["dd"],
                      "| hold", s["holdout"]["net"], s["holdout"]["pf"], "|", s["years"], flush=True)
            json.dump(out, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
