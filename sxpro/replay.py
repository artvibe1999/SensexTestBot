"""Signal replay on real Kite history (sanity check, NOT a P&L backtest).

    docker compose exec bot python -m sxpro.replay --days 30

For each strategy: number of signals that pass regime gating, and the share where
SENSEX moved in the signal direction over the next 6 candles (30 min).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta

from .config import IST, Config
from .kite_service import KiteService
from .market import build_context
from .strategies import ALL_STRATEGIES
from .strategies.base import sign


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    cfg = Config()
    kite = KiteService(cfg)
    if not kite.load_saved_token():
        raise SystemExit("Kite not logged in")
    kite.refresh_instruments()
    now = datetime.now(IST)
    df = kite.index_candles(now, "5minute", min(args.days + 7, 95))
    daily = kite.daily_candles(now, args.days + 40)
    stats = defaultdict(lambda: [0, 0])
    days = sorted(set(df.index.date))[-args.days:]
    for day in days:
        prev_rows = daily[daily.index.date < day]
        if prev_rows.empty:
            continue
        p = prev_rows.iloc[-1]
        prev = {"open": p.open, "high": p.high, "low": p.low, "close": p.close}
        pos = [i for i, ts in enumerate(df.index) if ts.date() == day]
        for i in pos[2:]:
            part = df.iloc[: i + 1]
            ctx = build_context(part, part.index[-1].to_pydatetime() + timedelta(minutes=5), prev)
            for s in ALL_STRATEGIES:
                if not s.in_window(ctx):
                    continue
                sig = s.entry(ctx)
                if sig and s.regime_ok(ctx, sig.direction, s.category):
                    fwd = df.iloc[i + 1: i + 7]
                    if len(fwd):
                        stats[s.sid][0] += 1
                        stats[s.sid][1] += int(sign(sig.direction) * (fwd["close"].iloc[-1] - part["close"].iloc[-1]) > 0)
    print(f"Replayed {len(days)} sessions")
    for s in ALL_STRATEGIES:
        n, hit = stats[s.sid]
        print(f"{s.sid:18s} signals={n:4d}  30-min direction hit={hit / n:.0%}" if n else f"{s.sid:18s} signals=   0")


if __name__ == "__main__":
    main()
