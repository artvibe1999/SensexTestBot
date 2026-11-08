"""Why does each strategy lose? Per-trade excursions from SENSEX 1-minute data.

usage: python diagnose.py DATA_DIR RESULTS_JSON OUT_JSON
For each trade: underlying move in ATR(14, 5m) units at entry -> MFE (best favourable
excursion) and MAE (worst adverse) while the trade was open, and the move at exit.
"""
import json
import re
import sys
from collections import Counter

import pandas as pd

from sxpro.backtest import Data

data_dir, res_path, out_path = sys.argv[1:4]
d = Data(data_dir)
res = json.load(open(res_path))
close1, high1, low1 = d.idx1["close"], d.idx1["high"], d.idx1["low"]
atr5 = d.enriched["atr"]
end5 = d.enriched.index + pd.Timedelta(minutes=5)


def group(reason: str) -> str:
    r = re.sub(r"\s*-?\d[\d,.]*", "", reason)
    r = re.sub(r"\(.*", "", r).strip()
    for k in ("underlying stop", "premium stop", "trailing stop", "target", "time exit", "max holding",
              "daily loss", "square-off", "closed beyond stop"):
        if k in r:
            return k
    return "strategy exit"


out = {}
for m in res["summary"][1:]:
    sid = m["strategy"]
    trades = res["trades"].get(sid, [])
    if not trades:
        continue
    rows = []
    for t in trades:
        et, xt = pd.Timestamp(t["entry_time"]), pd.Timestamp(t["exit_time"])
        d_ = 1 if t["option_type"] == "CE" else -1
        i = end5.searchsorted(et, side="right") - 1
        a = float(atr5.iloc[max(i, 0)]) or 1.0
        win = d.idx1[(d.idx1.index >= et.floor("min")) & (d.idx1.index < xt.ceil("min"))]
        if win.empty:
            continue
        e0 = float(win["open"].iloc[0])
        mfe = (win["high"].max() - e0) / a if d_ > 0 else (e0 - win["low"].min()) / a
        mae = (e0 - win["low"].min()) / a if d_ > 0 else (win["high"].max() - e0) / a
        at_exit = d_ * (float(win["close"].iloc[-1]) - e0) / a
        rows.append({"net": t["net_pnl"], "gross": t["gross_pnl"], "charges": t["charges"], "side": t["option_type"],
                     "hour": et.hour + (et.minute >= 30) * 0.5, "mfe": mfe, "mae": mae, "exit_atr": at_exit,
                     "reason": group(t["exit_reason"]), "hold": (xt - et).total_seconds() / 60,
                     "month": t["exit_time"][:7]})
    df = pd.DataFrame(rows)
    if df.empty:
        continue
    losers, winners = df[df.net <= 0], df[df.net > 0]
    side = df.groupby("side")["net"].agg(["count", "sum"]).round(0).to_dict("index")
    tod = df.assign(b=pd.cut(df.hour, [9, 10.5, 12, 13.5, 16], labels=["<10:30", "10:30-12", "12-13:30", ">13:30"]))
    tod = tod.groupby("b", observed=True)["net"].agg(["count", "sum"]).round(0).to_dict("index")
    out[sid] = {
        "trades": len(df), "net": round(df.net.sum()), "gross": round(df.gross.sum()), "charges": round(df.charges.sum()),
        "win_rate": round(100 * len(winners) / len(df), 1),
        "avg_win": round(winners.net.mean() if len(winners) else 0), "avg_loss": round(losers.net.mean() if len(losers) else 0),
        "loser_mfe_med": round(float(losers.mfe.median()), 2) if len(losers) else None,
        "loser_mae_med": round(float(losers.mae.median()), 2) if len(losers) else None,
        "winner_mfe_med": round(float(winners.mfe.median()), 2) if len(winners) else None,
        "winner_exit_atr_med": round(float(winners.exit_atr.median()), 2) if len(winners) else None,
        "losers_that_went_1atr_green_pct": round(100 * float((losers.mfe >= 1).mean()), 1) if len(losers) else None,
        "all_mfe_ge_2atr_pct": round(100 * float((df.mfe >= 2).mean()), 1),
        "exit_reasons": dict(Counter(df.reason).most_common()),
        "loss_by_reason": df[df.net <= 0].groupby("reason")["net"].sum().round(0).to_dict(),
        "side": side, "time_of_day": tod, "hold_med": round(float(df.hold.median()), 1),
    }
json.dump(out, open(out_path, "w"), indent=1, default=str)
print("diagnosed", len(out))
