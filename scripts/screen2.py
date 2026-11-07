"""Second research screen: entry families the 61-65 set lacks (same simulator and option
pricing as scripts/screen.py; train <= 2025-10-31, holdout after).

usage: python scripts/screen2.py DATA_DIR OUT_JSON [--families A,B] [--workers N]
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
from screen import minute  # noqa: E402


def sigma_bands(i, f, move, L, k):
    if i < L:
        return None
    sigma = move[i - L:i].mean(axis=0)
    return max(f["open"], f["pc"]) * (1 + k * sigma), min(f["open"], f["pc"]) * (1 - k * sigma)


def r_vwap_pb(i, f, frames, move, p):
    """Trend-day pullback: after a close outside the noise band, buy the first 5-min close
    back on the trend side after price touched VWAP (+/- tol x ATR)."""
    b = sigma_bands(i, f, move, 14, p["k"])
    if b is None:
        return []
    ub, lb = b
    c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
    atr = f["atr1"] * 5 ** 0.5
    trend, touched = 0, False
    for m in range(minute(time(9, 45)) - 1, minute(p["cutoff"]), 5):
        if trend == 0:
            if c[m] > ub[m] and c[m] > vw[m]:
                trend = 1
            elif c[m] < lb[m] and c[m] < vw[m]:
                trend = -1
            continue
        lo5, hi5 = l[m - 4:m + 1].min(), h[m - 4:m + 1].max()
        if (trend > 0 and lo5 <= vw[m] + p["tol"] * atr) or (trend < 0 and hi5 >= vw[m] - p["tol"] * atr):
            touched = True
        if touched and trend * (c[m] - vw[m]) > 0 and trend * (c[m] - c[m - 5]) > 0:
            stop = vw[m] - trend * p["stop_atr"] * atr
            return [(m, trend, stop, None)]
        if trend * (c[m] - vw[m]) < -2 * atr:
            return []   # trend failed
    return []


def r_nr_brk(i, f, frames, move, p):
    """Narrow-range day (yesterday's range the smallest of the last N): trade the break of
    the first R-minute range, either side, stop at the other side."""
    N, R = p["N"], p["R"]
    if i < N:
        return []
    rngs = [frames[j]["h"].max() - frames[j]["l"].min() for j in range(i - N, i)]
    if rngs[-1] > min(rngs):
        return []
    c, h, l = f["c"], f["h"], f["l"]
    hi, lo = h[:R].max(), l[:R].min()
    for m in range(R + 4, minute(p["cutoff"]), 5):
        if c[m] > hi:
            return [(m, 1, lo, None)]
        if c[m] < lo:
            return [(m, -1, hi, None)]
    return []


def r_pdc_reclaim(i, f, frames, move, p):
    """Gap away from the previous close, then a 5-min close back across it (after 09:45):
    trade in the reclaim direction; stop at the day's extreme on the gap side."""
    gap = f["open"] / f["pc"] - 1
    if abs(gap) < p["g"]:
        return []
    d = -1 if gap > 0 else 1
    c, h, l = f["c"], f["h"], f["l"]
    for m in range(minute(time(9, 45)) - 1, minute(p["cutoff"]), 5):
        if d * (c[m] - f["pc"]) > 0 and d * (c[m - 5] - f["pc"]) <= 0:
            stop = h[:m + 1].max() if d < 0 else l[:m + 1].min()
            return [(m, d, stop, None)]
    return []


def r_open_drive(i, f, frames, move, p):
    """Opening drive: first R minutes move > thr x prior range and close in the outer 25% of
    the opening range -> follow at R; stop at the opposite end of the range."""
    R = p["R"]
    c, h, l = f["c"], f["h"], f["l"]
    hi, lo = h[:R].max(), l[:R].min()
    mv = c[R - 1] - f["open"]
    if abs(mv) < p["thr"] * f["prev_range"] or hi - lo <= 0:
        return []
    pos = (c[R - 1] - lo) / (hi - lo)
    if mv > 0 and pos >= 0.75:
        return [(R - 1, 1, lo, None)]
    if mv < 0 and pos <= 0.25:
        return [(R - 1, -1, hi, None)]
    return []


def r_fade(i, f, frames, move, p):
    """Quiet-day fade: if yesterday's range < median of 20 days, fade a 5-min close beyond the
    noise band back toward VWAP (target VWAP, stop extreme + 0.5 ATR), 10:30-14:00."""
    if i < 20:
        return []
    med = np.median([frames[j]["h"].max() - frames[j]["l"].min() for j in range(i - 20, i)])
    if f["prev_range"] > med:
        return []
    b = sigma_bands(i, f, move, 14, p["k"])
    if b is None:
        return []
    ub, lb = b
    c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
    atr = f["atr1"] * 5 ** 0.5
    out = []
    for m in range(minute(time(10, 30)) - 1, minute(time(14, 0)), 5):
        if c[m] > ub[m] and c[m] < c[m - 5]:
            out.append((m, -1, h[:m + 1].max() + 0.5 * atr, vw[m]))
        elif c[m] < lb[m] and c[m] > c[m - 5]:
            out.append((m, 1, l[:m + 1].min() - 0.5 * atr, vw[m]))
    return out


def r_midday(i, f, frames, move, p):
    """Mid-session momentum: at `at`, beyond the noise band and on the VWAP side; hold."""
    b = sigma_bands(i, f, move, 14, p["k"])
    if b is None:
        return []
    ub, lb = b
    m = minute(p["at"]) - 1
    c, vw = f["c"], f["vwap"]
    if c[m] > ub[m] and c[m] > vw[m]:
        return [(m, 1, None, None)]
    if c[m] < lb[m] and c[m] < vw[m]:
        return [(m, -1, None, None)]
    return []


def r_inside_brk(i, f, frames, move, p):
    """Yesterday an inside day (high/low within the day before): break of yesterday's range."""
    if i < 2:
        return []
    y, yy = frames[i - 1], frames[i - 2]
    if not (y["h"].max() <= yy["h"].max() and y["l"].min() >= yy["l"].min()):
        return []
    c = f["c"]
    for m in range(minute(time(9, 30)) - 1, minute(p["cutoff"]), 5):
        if c[m] > f["ph"]:
            return [(m, 1, f["ph"] - p["buf"] * f["prev_range"], None)]
        if c[m] < f["pl"]:
            return [(m, -1, f["pl"] + p["buf"] * f["prev_range"], None)]
    return []


def r_hl_break(i, f, frames, move, p):
    """Intraday new day-high/low after 11:00 with the day beyond the noise band: follow."""
    b = sigma_bands(i, f, move, 14, p["k"])
    if b is None:
        return []
    ub, lb = b
    c, h, l, vw = f["c"], f["h"], f["l"], f["vwap"]
    for m in range(minute(p["start"]) - 1, minute(time(14, 30)), 5):
        hi, lo = h[:m - 4].max(), l[:m - 4].min()
        if c[m] > hi and c[m] > ub[m] and c[m] > vw[m]:
            return [(m, 1, vw[m], None)]
        if c[m] < lo and c[m] < lb[m] and c[m] < vw[m]:
            return [(m, -1, vw[m], None)]
    return []


T = lambda *a: [time(*x) for x in a]
FAMILIES = {
    "VWAP_PB": (r_vwap_pb, {"k": [0.75, 1.0, 1.25], "tol": [0.0, 0.5], "stop_atr": [1.0, 2.0],
                            "cutoff": T((13, 0), (14, 30)), "exit": ["eod", "trail"]}),
    "NR_BRK": (r_nr_brk, {"N": [4, 7], "R": [15, 30], "cutoff": T((12, 0), (14, 0)), "exit": ["eod", "trail", "vwap"]}),
    "PDC_RECLAIM": (r_pdc_reclaim, {"g": [0.002, 0.004, 0.007], "cutoff": T((11, 30), (13, 30)), "exit": ["eod", "trail", "vwap"]}),
    "OPEN_DRIVE": (r_open_drive, {"R": [10, 15, 30], "thr": [0.1, 0.2, 0.3], "exit": ["eod", "trail", "vwap"]}),
    "FADE": (r_fade, {"k": [1.0, 1.5, 2.0], "exit": ["eod"], "multi": [True], "last_entry": T((14, 0))}),
    "MIDDAY": (r_midday, {"at": T((11, 0), (11, 30), (12, 0), (12, 30), (13, 0)), "k": [0.75, 1.0, 1.25],
                          "exit": ["eod", "vwap"]}),
    "INSIDE_BRK": (r_inside_brk, {"cutoff": T((12, 0), (14, 0)), "buf": [0.1, 0.25], "exit": ["eod", "trail", "vwap"]}),
    "HL_BREAK": (r_hl_break, {"k": [0.75, 1.0, 1.25], "start": T((11, 0), (12, 0)), "exit": ["eod", "trail", "vwap"]}),
}

CTX: dict = {}


def init(data):
    days, daily, vix, vol = S.load(data)
    frames, move = S.day_frames(days, daily, vol)
    CTX.update(frames=frames, move=move, pricer=S.Pricer(vix, S.expiries([f["day"] for f in frames])))


def run(job):
    fam, p = job
    rule = FAMILIES[fam][0]
    tr = S.simulate(CTX["frames"], CTX["move"], CTX["pricer"], rule, dict(p))
    s = S.stats(tr, date(2025, 10, 31))
    if not s:
        return None
    return {"family": fam, "params": {k: (v.strftime("%H:%M") if isinstance(v, time) else v) for k, v in p.items()}, **s}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("out")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--workers", type=int, default=9)
    a = ap.parse_args()
    jobs = []
    for fam in a.families.split(","):
        grid = FAMILIES[fam][1]
        keys = list(grid)
        jobs += [(fam, dict(zip(keys, combo))) for combo in itertools.product(*(grid[k] for k in keys))]
    print("variants:", len(jobs), flush=True)
    res = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=init, initargs=(a.data,)) as ex:
        for r in ex.map(run, jobs, chunksize=2):
            if r:
                res.append(r)
                print(r["family"], r["params"], r["train"]["trades"], r["train"]["net"], r["train"]["pf"], "| holdout",
                      r["holdout"]["trades"], r["holdout"]["net"], r["holdout"]["pf"], flush=True)
    json.dump({"results": res}, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
