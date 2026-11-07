"""Backtest-derived adjustments for strategies (see Strategy.apply_tuning).

Chosen on the in-sample period and kept only when they also held up out of sample;
see docs/backtest_tuning.md. Override for experiments with SXPRO_TUNING (a JSON
object {sid: {...}}, or a path to a JSON file); its entries replace these per strategy.
"""
from __future__ import annotations

import json
import os

# Evaluation order of the enabled best-6 set (one position at a time, so order decides which
# signal gets the slot on the same candle). Chosen by a greedy build on Sep 2022 - Oct 2025
# only; see docs/research_66_79.md.
TUNING: dict[str, dict] = {
    "SENSEX_NOISE_61": {"priority": 1},
    "SENSEX_ORB60_74": {"priority": 2},
    "SENSEX_INSIDE_71": {"priority": 3},
    "SENSEX_3DAY_75": {"priority": 4},
    "SENSEX_LATEMOM_63": {"priority": 5},
    "SENSEX_HLBRK_66": {"priority": 6},
}


def load_overrides() -> dict[str, dict]:
    raw = os.environ.get("SXPRO_TUNING", "").strip()
    if not raw:
        return {}
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(raw)


def apply(strategies) -> None:
    table = {**TUNING, **load_overrides()}
    for s in strategies:
        s.tune = dict(table.get(s.sid, {}))
