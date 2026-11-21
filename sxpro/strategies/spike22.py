"""SENSEX_SPIKE_22 — Opening Premium Spike Chase (tick-driven; ported from sensex-pro-bot)."""
from __future__ import annotations

from datetime import time

from .base import BREAKOUT, Strategy


class OpeningPremiumSpike(Strategy):
    """Buy the first near-ATM CE or PE whose streamed premium (mid) rises >= 8% above its
    10-second low between 09:15:20 and 09:30 (spread <= 0.8%, strike within 150 points of spot).
    Exit: -6% premium stop or 5 minutes while not in profit; at +12% the 5-minute cap is lifted
    and a trail 25% under the peak premium (never below entry +1%) runs for the rest of the day.
    Off at every start; armed only by "/enable SPIKE_22" for the current mode (a /mode switch
    disarms it); a single trade, after which it disables itself. Paper or live."""
    sid, name, category = "SENSEX_SPIKE_22", "Opening Premium Spike Chase", BREAKOUT
    start, end, time_exit, max_hold_min = time(9, 15, 20), time(9, 30), time(15, 15), 330
    prem_min, prem_max = 1, 5000          # the strike comes from the trigger, not the selector
    expiry_rule = "nearest"
    reentry = "no"
    trail_kind = "none"
    priority = 999
    spike_pct, spike_window_s, spike_max_spread, spike_near_points = 0.08, 10.0, 0.008, 150.0
    prem_sl, prem_arm, prem_trail, prem_max_hold_s, prem_trail_floor = 0.06, 0.12, 0.25, 300, 0.01

    def in_window(self, ctx) -> bool:
        return False                      # never evaluated on candle closes

    def entry(self, ctx):
        return None

    def describe(self) -> str:
        return (f"{self.sid} – {self.name} [tick] {self.start:%H:%M:%S}-{self.end:%H:%M} "
                f"spike {self.spike_pct:.0%}/{self.spike_window_s:.0f}s exit SL{self.prem_sl:.0%}/"
                f"{self.prem_max_hold_s // 60}min, profit trail {self.prem_trail:.0%} from +{self.prem_arm:.0%}; "
                f"1 trade, /enable SPIKE_22 to arm")
