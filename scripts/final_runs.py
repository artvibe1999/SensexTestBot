"""Final combined backtests: untuned profitable set, profitable + validated adjusted
strategies (full year and out-of-sample only). usage: python final_runs.py DATA SOLO_JSON TUNE_JSON OUT_JSON"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor

from sxpro.backtest import metrics, run_one

CAPITAL, LOTS = 50000, 2


def job(a):
    label, data, enabled, tune, period = a
    r = run_one((data, tuple(enabled), CAPITAL, LOTS, tune, period))
    return label, metrics(r), r["trades"]


if __name__ == "__main__":
    data, solo_p, tune_p, out_p = sys.argv[1:5]
    solo = json.load(open(solo_p))["summary"][1:]
    profitable = [m["strategy"] for m in solo if m["net"] > 0]
    t = json.load(open(tune_p))
    cands, res = t["candidates"], t["results"]
    adopted = {}
    for sid, r in res.items():
        pick = r.get("pick")
        if not pick or pick not in r["out"]:
            continue
        o = r["out"][pick]
        if o["net"] > 0 and (o["profit_factor"] is None or o["profit_factor"] >= 1.0) and o["trades"] >= 3:
            adopted[sid] = cands[pick]
    final = profitable + [s for s in adopted if s not in profitable]
    oos = tuple(t["out_sample"])
    jobs = [("profitable_untuned_full", data, profitable, {}, None),
            ("final_full", data, final, adopted, None),
            ("final_out_of_sample", data, final, adopted, oos),
            ("profitable_untuned_out_of_sample", data, profitable, {}, oos)]
    out = {"profitable": profitable, "adopted": adopted, "final": final, "runs": {}}
    with ProcessPoolExecutor(max_workers=4) as ex:
        for label, m, trades in ex.map(job, jobs):
            out["runs"][label] = {"metrics": m, "trades": trades}
            print(label, m["trades"], m["win_rate"], m["net"], m["profit_factor"], m["max_drawdown"], flush=True)
    json.dump(out, open(out_p, "w"), indent=1, default=str)
