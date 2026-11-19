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
    # Original 6 verified strategies
    "SENSEX_NOISE_61", "SENSEX_ORB60_74", "SENSEX_INSIDE_71",
    "SENSEX_3DAY_75", "SENSEX_LATEMOM_63", "SENSEX_HLBRK_66",
    # Data-verified additions from 28-day GCS archive analysis (2026-11-20)
    "SENSEX_FRACTAL_BRK_35",
    "SENSEX_VBOL_79",
    "SENSEX_ORB30_65",
    "SENSEX_MTF_ALIGN_55",
    "SENSEX_FIRST30_77",
    "SENSEX_ODRIVE_69",
    "SENSEX_LUNCH_73",
    "SENSEX_PDB_64",
    "SENSEX_VWAPPB_70",
    "SENSEX_VBO_62",
    "SENSEX_HDIV_47",
    "SENSEX_THRUST_72",
    "SENSEX_MIDDAY_68",
    "SENSEX_MIDDAY_67",
    "SENSEX_CLOSESTR_76",
]
VERIFIED_INDEX: dict[str, int] = {sid: i + 1 for i, sid in enumerate(VERIFIED_ORDER)}

# Default deny: only the verified set is enabled on first boot, and once on existing
# installs at Engine startup (store flag DEFAULT_DENY_FLAG) every other strategy is
# switched off. /enable can still switch one on afterwards (it ranks after the verified set).
DEFAULT_DENY_FLAG = "default_deny_2026_11_09_applied"

# Retired after the 2026-11-09 structural review (lagging crossovers, naked oscillators,
# rigid time blocks, 0DTE gamma exposure); /enable warns before switching one on.
RETIRED: tuple[str, ...] = (
    "SENSEX_WMA_13", "SENSEX_RNG_14", "SENSEX_EMA_TWIST_33", "SENSEX_TEMA_ALIGN_49",
    "SENSEX_EOD_IMB_51", "SENSEX_VWAP_X_16", "SENSEX_MACD_17", "SENSEX_TREND_EXH_30",
    "SENSEX_0DTE_12", "SENSEX_VWAP_PIN_28", "SENSEX_GAMMA_SQR_39", "SENSEX_FIB_19",
)

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
