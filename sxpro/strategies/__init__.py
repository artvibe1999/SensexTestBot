from .catalog import ALL_STRATEGIES, STRATEGY_MAP
from .admve import AdaptiveDirectionalMomentum

# ADMVE is a research candidate, deliberately not in the verified set: it starts disabled
# (default deny, also on existing installs via Engine's known_strategies record) and ranks
# after the verified set once enabled.
ADMVE = AdaptiveDirectionalMomentum()
ALL_STRATEGIES.append(ADMVE)
STRATEGY_MAP[ADMVE.sid] = ADMVE

__all__ = ["ALL_STRATEGIES", "STRATEGY_MAP", "apply_selection_overrides"]

# Spec values, kept so overrides are idempotent and can be reported.
SPEC_LIMITS = {s.sid: (s.prem_min, s.prem_max, s.delta_min, s.delta_max) for s in ALL_STRATEGIES}


def apply_selection_overrides(cfg) -> None:
    """Raise premium caps and widen delta bands beyond the spec (user request).

    Each strategy keeps its spec delta *target*, so the spec strike is still preferred;
    the wider limits only let the selector fall back to pricier / deeper-ITM strikes
    when the preferred strike's premium is above the old cap.
    """
    for s in ALL_STRATEGIES:
        pmin, pmax, dmin, dmax = SPEC_LIMITS[s.sid]
        cap = cfg.zero_dte_premium_cap if s.expiry_rule == "0dte" else cfg.premium_cap
        s.prem_max = max(pmax, cap)
        s.delta_max = round(min(cfg.delta_max_cap, dmax + cfg.delta_widen_up), 2)
        s.delta_min = round(max(cfg.delta_min_floor, dmin - cfg.delta_widen_down), 2)
