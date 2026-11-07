import json, sys, collections
for path in sys.argv[1:]:
    d = json.load(open(path))
    for label, r in d["runs"].items():
        t = r["trades"]
        yr = collections.defaultdict(float); ho = [x["net_pnl"] for x in t if x["exit_time"][:10] >= "2025-11-01"]
        tr = [x["net_pnl"] for x in t if x["exit_time"][:10] < "2025-11-01"]
        for x in t: yr[x["exit_time"][:4]] += x["net_pnl"]
        pf = lambda v: round(sum(a for a in v if a > 0) / -sum(a for a in v if a <= 0), 2) if any(a <= 0 for a in v) else None
        hm = collections.defaultdict(float)
        for x in t:
            if x["exit_time"][:10] >= "2025-11-01": hm[x["exit_time"][:7]] += x["net_pnl"]
        neg = sum(1 for v in hm.values() if v < 0)
        print(f"{label:22s} train n={len(tr)} net={sum(tr):>10,.0f} pf={pf(tr)} | holdout n={len(ho)} net={sum(ho):>9,.0f} pf={pf(ho)} losing months {neg}/{len(hm)} | years " + " ".join(f"{k}:{v/1000:+.0f}k" for k, v in sorted(yr.items())))
