import json, sys
from concurrent.futures import ProcessPoolExecutor
from sxpro.backtest import metrics, run_one
COMBOS = {"noise_latemom": ["SENSEX_NOISE_61", "SENSEX_LATEMOM_63"],
          "noise_vbo": ["SENSEX_VBO_62", "SENSEX_NOISE_61"],
          "noise_orb30": ["SENSEX_NOISE_61", "SENSEX_ORB30_65"],
          "noise_vbo_latemom": ["SENSEX_VBO_62", "SENSEX_NOISE_61", "SENSEX_LATEMOM_63"],
          "noise_first_all5": ["SENSEX_NOISE_61", "SENSEX_VBO_62", "SENSEX_ORB30_65", "SENSEX_PDB_64", "SENSEX_LATEMOM_63"]}
def job(a):
    label, data, en = a
    r = run_one((data, tuple(en), 50000, 2))
    return label, metrics(r), r["trades"]
if __name__ == "__main__":
    data, out_p = sys.argv[1:3]
    out = {"combos": COMBOS, "runs": {}}
    with ProcessPoolExecutor(max_workers=len(COMBOS)) as ex:
        for label, m, t in ex.map(job, [(k, data, v) for k, v in COMBOS.items()]):
            out["runs"][label] = {"metrics": m, "trades": t}
            print(label, m["trades"], m["win_rate"], m["net"], m["profit_factor"], m["max_drawdown"], flush=True)
    json.dump(out, open(out_p, "w"), indent=1, default=str)
