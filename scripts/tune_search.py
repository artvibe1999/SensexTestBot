"""Walk-forward adjustment search for losing strategies.

usage: python tune_search.py DATA_DIR SIDS(comma) OUT_JSON [workers]
Every candidate adjustment is replayed solo on the in-sample period; the best one per
strategy (most net P&L with >= MIN_TRADES trades and PF >= MIN_PF) is then replayed on the
out-of-sample period. Capital 50,000, fixed 2 lots (same as the main backtest).
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from sxpro.backtest import metrics, run_one

IN_SAMPLE = ("2025-11-06", "2026-06-30")
OUT_SAMPLE = ("2026-07-01", "2026-11-06")
CAPITAL, LOTS = 50000, 2
MIN_TRADES, MIN_PF = 8, 1.15

# Each candidate answers one diagnosis: wrong-way trades (trend15/side), chop (adx_min),
# stops inside normal noise (min_stop_atr), targets rarely reached / profits given back
# (rr, book), exits that cut winners (no_target), stale trades (max_hold), bad hours (window).
CANDIDATES = {
    "baseline": {},
    "trend15": {"trend15": True},                         # losers move against at once -> trade with 15m trend
    "adx20": {"adx_min": 20},                             # avoid chop
    "stop1atr": {"min_stop_atr": 1.0},                    # stop inside noise
    "rr1_book": {"rr": 1.0, "book": 0.5},                 # losers were green first -> bank half at 1R
    "rr1.5_book": {"rr": 1.5, "book": 0.5},
    "trail_only": {"no_target": True},                    # winners exit well below their MFE
    "no_late": {"end": "13:30"},                          # afternoon losses
    "morning": {"end": "12:00"},
    "midday": {"start": "10:00", "end": "13:30"},
    "calls": {"side": "CE"},                              # one side carries the loss
    "puts": {"side": "PE"},
    "trend15_rr1.5_book": {"trend15": True, "rr": 1.5, "book": 0.5},
    "trend15_no_late": {"trend15": True, "end": "13:30"},
}


def job(args):
    data, sid, name, tune, period = args
    r = run_one((data, sid, CAPITAL, LOTS, {sid: tune} if tune else {}, period))
    m = metrics(r)
    return sid, name, {k: m[k] for k in ("trades", "win_rate", "net", "profit_factor", "max_drawdown", "avg_win", "avg_loss")}


if __name__ == "__main__":
    DATA, sids, out = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 11
    res: dict = {s: {"in": {}, "out": {}} for s in sids}
    # reuse in-sample results already computed elsewhere: lines "IN  sid name trades net pf"
    prev = os.environ.get("PREV_LOG")
    if prev and os.path.exists(prev):
        for line in open(prev, encoding="utf-8"):
            parts = line.split()
            if len(parts) == 6 and parts[0] == "IN" and parts[1] in res and parts[2] in CANDIDATES:
                pf = None if parts[5] == "None" else float(parts[5])
                res[parts[1]]["in"][parts[2]] = {"trades": int(parts[3]), "net": float(parts[4]), "profit_factor": pf,
                                                  "reused": True}
    jobs = [(DATA, s, n, t, IN_SAMPLE) for s in sids for n, t in CANDIDATES.items() if n not in res[s]["in"]]
    print("in-sample jobs to run:", len(jobs), flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for sid, name, m in ex.map(job, jobs, chunksize=1):
            res[sid]["in"][name] = m
            print("IN ", sid, name, m["trades"], m["net"], m["profit_factor"], flush=True)
        picks = []
        for sid in sids:
            ok = [(n, m) for n, m in res[sid]["in"].items()
                  if n != "baseline" and m["trades"] >= MIN_TRADES and (m["profit_factor"] or 0) >= MIN_PF and m["net"] > 0]
            ok.sort(key=lambda nm: nm[1]["net"], reverse=True)
            res[sid]["pick"] = ok[0][0] if ok else None
            for n in ([ok[0][0]] if ok else []) + ["baseline"]:
                picks.append((DATA, sid, n, CANDIDATES[n], OUT_SAMPLE))
        for sid, name, m in ex.map(job, picks, chunksize=1):
            res[sid]["out"][name] = m
            print("OUT", sid, name, m["trades"], m["net"], m["profit_factor"], flush=True)
    json.dump({"in_sample": IN_SAMPLE, "out_sample": OUT_SAMPLE, "candidates": CANDIDATES, "results": res},
              open(out, "w"), indent=1)
