"""Backtest-derived adjustments for strategies (see Strategy.apply_tuning).

Chosen on the in-sample period and kept only when they also held up out of sample;
see docs/backtest_tuning.md. Override for experiments with SXPRO_TUNING (a JSON
object {sid: {...}}, or a path to a JSON file); its entries replace these per strategy.
"""
from __future__ import annotations

import json
import os

TUNING: dict[str, dict] = {}


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
