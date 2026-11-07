"""Run engine backtests from a jobs file, appending one JSON line per finished job.

usage: python scripts/jobs4y.py DATA JOBS_JSON OUT_JSONL [workers]
JOBS_JSON: [{"label": str, "enabled": sid | [sids], "tune": {sid: {...}} (optional)}, ...]
Jobs whose label is already in OUT_JSONL are skipped (resumable). ₹50k capital, 2 lots,
full data range; each line holds metrics for all / train (<= 2025-10-31) / holdout and the trades.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from sxpro.backtest import run_one

TRAIN_END = "2025-11-01"


def part(trades):
    nets = [t["net_pnl"] for t in trades]
    g, l = sum(x for x in nets if x > 0), -sum(x for x in nets if x <= 0)
    eq, peak, dd = 0.0, 0.0, 0.0
    for x in nets:
        eq += x; peak = max(peak, eq); dd = max(dd, peak - eq)
    return {"trades": len(nets), "net": round(sum(nets)), "pf": round(g / l, 2) if l > 0 else None,
            "win": round(100 * sum(x > 0 for x in nets) / len(nets), 1) if nets else 0, "dd": round(dd)}


def job(j):
    en = j["enabled"]
    r = run_one((DATA, en if isinstance(en, str) else tuple(en), 50000, 2, j.get("tune") or {}))
    t = sorted(r["trades"], key=lambda x: x["exit_time"])
    years = {}
    for x in t:
        years[x["exit_time"][:4]] = years.get(x["exit_time"][:4], 0) + x["net_pnl"]
    slim = [{k: x[k] for k in ("strategy", "option_type", "entry_time", "exit_time", "net_pnl", "exit_reason")} for x in t]
    return {"label": j["label"], "enabled": en, "tune": j.get("tune") or {},
            "all": part(t), "train": part([x for x in t if x["exit_time"] < TRAIN_END]),
            "holdout": part([x for x in t if x["exit_time"] >= TRAIN_END]),
            "years": {k: round(v) for k, v in sorted(years.items())}, "skips": r["skips"], "trades": slim}


DATA = sys.argv[1]
if __name__ == "__main__":
    jobs_p, out_p = sys.argv[2], sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 9
    done = set()
    if os.path.exists(out_p):
        done = {json.loads(l)["label"] for l in open(out_p) if l.strip()}
    jobs = [j for j in json.load(open(jobs_p)) if j["label"] not in done]
    print("jobs to run:", len(jobs), flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex, open(out_p, "a") as out:
        futs = [ex.submit(job, j) for j in jobs]
        for f in as_completed(futs):
            r = f.result()
            out.write(json.dumps(r, default=str) + "\n"); out.flush()
            print(r["label"], "| all", r["all"]["trades"], r["all"]["net"], r["all"]["pf"], "| train", r["train"]["net"],
                  r["train"]["pf"], "| hold", r["holdout"]["net"], r["holdout"]["pf"], flush=True)
