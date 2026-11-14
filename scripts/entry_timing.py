"""4-year engine backtest of the verified six with the experimental switches
(tranche-fit-experiment branch). Each job sets env vars before run_one builds its Config."""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from sxpro.backtest import run_one
from sxpro.strategies.tuning import VERIFIED_ORDER

DATA, OUT = sys.argv[1], sys.argv[2]
TRAIN_END = "2025-11-01"
# Limits pinned to Rs 50k capital (as live today): capital_info returns 50,000 for the %
# limits (trade cap, daily/weekly limit) while margin still uses the real paper balance;
# emergency protection still compares the real balance with its peak.
from sxpro.engine import Engine
from sxpro.risk import RiskManager

PIN = 50000.0
_emerg = RiskManager.emergency


async def _capital_info(self, mode):
    bal = self.risk.paper_balance()
    used = sum(p["entry_price"] * p["qty"] for p in self.positions if p["mode"] == mode)
    return PIN, bal - used


Engine.capital_info = _capital_info
RiskManager.emergency = lambda self, mode, capital: _emerg(self, mode, self.paper_balance())

JOBS = [
    ("base", {}),
    ("ext 1.5", {"ENTRY_EXT_MAX_ATR": 1.5}),
    ("ext 2.0", {"ENTRY_EXT_MAX_ATR": 2.0}),
    ("ext 2.5", {"ENTRY_EXT_MAX_ATR": 2.5}),
    ("run 2", {"ENTRY_RUN_MAX_ATR": 2.0}),
    ("run 3", {"ENTRY_RUN_MAX_ATR": 3.0}),
    ("pb 0.3/30", {"ENTRY_PULLBACK_ATR": 0.3, "ENTRY_PULLBACK_MIN": 30}),
    ("pb 0.5/30", {"ENTRY_PULLBACK_ATR": 0.5, "ENTRY_PULLBACK_MIN": 30}),
    ("pb 0.75/45", {"ENTRY_PULLBACK_ATR": 0.75, "ENTRY_PULLBACK_MIN": 45}),
    ("pb 1.0/60", {"ENTRY_PULLBACK_ATR": 1.0, "ENTRY_PULLBACK_MIN": 60}),
]


KEYS = ("ENTRY_EXT_MAX_ATR", "ENTRY_RUN_MAX_ATR", "ENTRY_PULLBACK_ATR", "ENTRY_PULLBACK_MIN", "TRADE_LOSS_CAP_PCT", "DAILY_LOSS_LIMIT_PCT", "SLIPPAGE_BUFFER_PTS", "AUTO_MAX_LOTS",
        "TRANCHE_RISK_RS", "MIN_MARKET_FIT")


def part(trades):
    nets = [t["net_pnl"] for t in trades]
    g, l = sum(x for x in nets if x > 0), -sum(x for x in nets if x <= 0)
    eq = peak = dd = 0.0
    for x in nets:
        eq += x; peak = max(peak, eq); dd = max(dd, peak - eq)
    w = [x for x in nets if x > 0]; ls = [x for x in nets if x <= 0]
    return {"trades": len(nets), "net": round(sum(nets)), "pf": round(g / l, 2) if l > 0 else None,
            "win": round(100 * len(w) / len(nets), 1) if nets else 0, "dd": round(dd),
            "avg_win": round(np.mean(w)) if w else 0, "avg_loss": round(np.mean(ls)) if ls else 0,
            "worst": round(min(nets)) if nets else 0}


def job(spec):
    label, env = spec
    for k in KEYS:
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in env.items()})
    r = run_one((DATA, tuple(VERIFIED_ORDER), 50000, 2, {}))
    t = sorted(r["trades"], key=lambda x: x["exit_time"])
    years, by_strat, reasons, days = {}, {}, {}, {}
    for x in t:
        years[x["exit_time"][:4]] = years.get(x["exit_time"][:4], 0) + x["net_pnl"]
        by_strat[x["strategy"]] = by_strat.get(x["strategy"], 0) + x["net_pnl"]
        k = x["exit_reason"].split("(")[0].split(" SENSEX")[0].strip()
        k = "premium stop" if k.startswith("premium stop") else k
        reasons[k] = reasons.get(k, 0) + 1
        days[x["trade_day"]] = days.get(x["trade_day"], 0) + x["net_pnl"]
    skips = dict(sorted(r["skips"].items(), key=lambda kv: -kv[1])[:8])
    return {"label": label, "env": env, "all": part(t), "train": part([x for x in t if x["exit_time"] < TRAIN_END]),
            "holdout": part([x for x in t if x["exit_time"] >= TRAIN_END]),
            "years": {k: round(v) for k, v in sorted(years.items())},
            "by_strategy": {k: round(v) for k, v in sorted(by_strat.items())},
            "worst_day": round(min(days.values())) if days else 0,
            "days_le_minus5k": sum(v <= -5000 for v in days.values()),
            "reasons": reasons, "skips": skips,
            "entries_per_day": {str(n): sum(1 for v in __import__("collections").Counter(x["trade_day"] for x in t).values() if v == n) for n in (1, 2, 3)},
            "lots": {str(q // 20): sum(1 for x in t if x["qty"] // 20 == q // 20) for q in sorted({x["qty"] for x in t})}}


if __name__ == "__main__":
    pick = [JOBS[int(i)] for i in sys.argv[3].split(",")] if len(sys.argv) > 3 else JOBS
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    with ProcessPoolExecutor(workers) as ex, open(OUT, "a") as fh:
        for res in ex.map(job, pick):
            fh.write(json.dumps(res) + "\n"); fh.flush()
            print(json.dumps({k: res[k] for k in ("label", "all", "holdout", "worst_day", "days_le_minus5k")}), flush=True)
