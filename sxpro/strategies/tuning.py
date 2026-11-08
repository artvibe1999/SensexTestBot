"""Verified strategy set and backtest-derived adjustments (see Strategy.apply_tuning).

VERIFIED_ORDER is the backtest-verified set in evaluation order (one position at a time,
so the order decides which signal gets the slot). It was chosen by a greedy build on
Sep 2022 - Oct 2025 only; see docs/research_66_79.md. The engine always ranks these ahead
of any other enabled strategy (e.g. one switched on later with /enable).

TUNING holds per-strategy adjustments. Override for experiments with SXPRO_TUNING (a JSON
object {sid: {...}}, or a path to a JSON file); its keys are merged into these per strategy.
"""
from __future__ import annotations

import json
import os

VERIFIED_ORDER: list[str] = [
    "SENSEX_NOISE_61", "SENSEX_ORB60_74", "SENSEX_INSIDE_71",
    "SENSEX_3DAY_75", "SENSEX_LATEMOM_63", "SENSEX_HLBRK_66",
]
VERIFIED_INDEX: dict[str, int] = {sid: i + 1 for i, sid in enumerate(VERIFIED_ORDER)}

TUNING: dict[str, dict] = {}


def load_overrides() -> dict[str, dict]:
    raw = os.environ.get("SXPRO_TUNING", "").strip()
    if not raw:
        return {}
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(raw)


def merged(*tables: dict) -> dict[str, dict]:
    """Merge {sid: {key: value}} tables; later tables win per key, not per strategy."""
    out: dict[str, dict] = {}
    for table in tables:
        for sid, keys in (table or {}).items():
            out[sid] = {**out.get(sid, {}), **keys}
    return out


def apply(strategies) -> None:
    table = merged(TUNING, load_overrides())
    for s in strategies:
        s.tune = dict(table.get(s.sid, {}))
