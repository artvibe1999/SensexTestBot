"""Run research + combined engine backtests in parallel. usage: python vm_runs.py DATA SOLO50_JSON OUT"""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from sxpro.backtest import metrics, run_one

def job(a):
    label, data, enabled = a
    r = run_one((data, enabled if isinstance(enabled, str) else tuple(enabled), 50000, 2))
    return label, metrics(r), r["trades"]

if __name__ == "__main__":
    data, solo_p, out_p = sys.argv[1:4]
    from sxpro.strategies.catalog_research import STRATEGIES_61_65
    research = [s.sid for s in STRATEGIES_61_65]
    prof26 = [m["strategy"] for m in json.load(open(solo_p))["summary"][1:] if m["net"] > 0]
    jobs = [(sid, data, sid) for sid in research] + [("research_5", data, research),
            ("research_5_plus_26", data, research + prof26), ("profitable_26", data, prof26)]
    out = {"research": research, "profitable_26": prof26, "runs": {}}
    with ProcessPoolExecutor(max_workers=len(jobs)) as ex:
        for label, m, t in ex.map(job, jobs):
            out["runs"][label] = {"metrics": m, "trades": t}
            print(label, m["trades"], m["win_rate"], m["net"], m["profit_factor"], m["max_drawdown"], flush=True)
    json.dump(out, open(out_p, "w"), indent=1, default=str)
