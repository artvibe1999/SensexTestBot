"""Capital Management Framework (framework section 1).

Limits are expressed as fractions of current capital so they scale with the
paper capital set from Telegram or with the live funds fetched from Zerodha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .config import IST, Config
from .store import Store


def week_start(d: datetime) -> str:
    return (d.date() - timedelta(days=d.weekday())).isoformat()


@dataclass
class SizeResult:
    lots: int
    qty: int
    hard_stop: float
    alloc: float
    max_loss: float
    reason: str = ""


class RiskManager:
    def __init__(self, cfg: Config, store: Store, clock=None):
        self.cfg = cfg
        self.store = store
        self.clock = clock or (lambda: datetime.now(IST))

    # ---------------- capital ----------------
    def paper_balance(self) -> float:
        return float(self.store.get("paper_balance", self.cfg.default_paper_capital))

    def set_paper_capital(self, amount: float) -> None:
        self.store.set("paper_capital", amount)
        self.store.set("paper_balance", amount)
        self.store.set("paper_peak", amount)
        self.store.set("paper_streak_reset_id", self._last_trade_id("paper"))
        self.store.set("paper_cooldown_until", None)

    def on_trade_closed(self, mode: str, net_pnl: float, equity_after: float | None = None) -> None:
        if mode == "paper":
            bal = self.paper_balance() + net_pnl
            self.store.set("paper_balance", round(bal, 2))
            equity_after = bal
        if equity_after is not None:
            peak = float(self.store.get(f"{mode}_peak", equity_after) or equity_after)
            self.store.set(f"{mode}_peak", max(peak, equity_after))
        # consecutive-loss cool-off
        streak = self.loss_streak(mode)
        if streak >= self.cfg.max_consecutive_losses:
            until = self.clock() + timedelta(hours=self.cfg.cooloff_hours)
            self.store.set(f"{mode}_cooldown_until", until.isoformat())
            self.store.set(f"{mode}_streak_reset_id", self._last_trade_id(mode))

    def update_live_peak(self, equity: float) -> None:
        peak = float(self.store.get("live_peak", 0) or 0)
        if equity > peak:
            self.store.set("live_peak", equity)

    def emergency(self, mode: str, capital: float) -> bool:
        peak = float(self.store.get(f"{mode}_peak", capital) or capital)
        return capital < peak * (1 - self.cfg.emergency_drawdown_pct)

    # ---------------- limits ----------------
    def _last_trade_id(self, mode: str) -> int:
        return self.store.last_trade_id(mode)

    def loss_streak(self, mode: str) -> int:
        reset_id = int(self.store.get(f"{mode}_streak_reset_id", 0) or 0)
        streak = 0
        for t in self.store.recent_trades(mode, self.cfg.max_consecutive_losses + 1):
            if t["id"] <= reset_id:
                break
            if t["net_pnl"] < 0:
                streak += 1
            else:
                break
        return streak

    def day_stats(self, mode: str, now: datetime) -> dict:
        day = now.date().isoformat()
        trades = self.store.trades(mode, since_day=day, until_day=day)
        entries = int(self.store.get(f"{mode}_entries_{day}", 0) or 0)
        return {
            "realized": round(sum(t["net_pnl"] for t in trades), 2),
            "closed": len(trades),
            "entries": entries,
            "week_realized": round(self.store.realized_pnl(mode, since_day=week_start(now)), 2),
        }

    def note_entry(self, mode: str, now: datetime) -> None:
        key = f"{mode}_entries_{now.date().isoformat()}"
        self.store.set(key, int(self.store.get(key, 0) or 0) + 1)

    def can_open(self, mode: str, capital: float, now: datetime, unrealized: float = 0.0) -> tuple[bool, str]:
        if capital <= 0:
            return False, "no capital available"
        st = self.day_stats(mode, now)
        if st["entries"] >= self.cfg.max_trades_per_day:
            return False, f"max {self.cfg.max_trades_per_day} trades/day reached"
        if st["realized"] + unrealized <= -self.cfg.max_daily_loss_pct * capital:
            return False, f"daily loss limit {self.cfg.max_daily_loss_pct:.0%} hit"
        if st["week_realized"] + unrealized <= -self.cfg.max_weekly_loss_pct * capital:
            return False, f"weekly loss limit {self.cfg.max_weekly_loss_pct:.0%} hit"
        until = self.store.get(f"{mode}_cooldown_until")
        if until and datetime.fromisoformat(until) > now:
            return False, f"cool-off after {self.cfg.max_consecutive_losses} losses until {until[:16]}"
        return True, ""

    def daily_loss_breached(self, mode: str, capital: float, now: datetime, unrealized: float) -> bool:
        st = self.day_stats(mode, now)
        return st["realized"] + unrealized <= -self.cfg.max_daily_loss_pct * capital

    # ---------------- sizing ----------------
    def size(self, mode: str, capital: float, available: float, premium: float, lot_size: int,
             capital_pct: float, lots_setting: str | int,
             strategy_prem_stop: Optional[float]) -> SizeResult:
        """Position sizing: Floor(Allocated Margin / (Premium * Lot Size)).

        Allocated margin = available margin x MARGIN_UTILIZATION_PCT (90%), scaled by the
        strategy's share (0DTE uses half) and halved under emergency protection.
        lots_setting == "auto" -> that formula; integer -> user-fixed lots. Both are bounded by
        the allocated margin; the per-trade loss cap sets the hard premium stop.
        """
        alloc = max(0.0, available) * self.cfg.alloc_pct * (capital_pct / 0.10)
        if self.emergency(mode, capital):
            alloc /= 2
        max_loss = capital * self.cfg.max_risk_per_trade_pct
        unit_cost = premium * lot_size
        if unit_cost <= 0:
            return SizeResult(0, 0, 0, alloc, max_loss, "invalid premium")
        afford_lots = math.floor(alloc / unit_cost)
        if lots_setting == "auto":
            lots = min(afford_lots, self.cfg.max_lots_cap)
        else:
            lots = int(lots_setting)
        lots = min(lots, afford_lots)
        if lots <= 0:
            why = (f"allocated margin ₹{alloc:,.0f} too small for 1 lot at ₹{premium:.1f} x {lot_size}")
            return SizeResult(0, 0, 0, alloc, max_loss, why)
        qty = lots * lot_size
        cap_stop = premium - max_loss / qty
        hard_stop = max(cap_stop, strategy_prem_stop) if strategy_prem_stop else cap_stop
        hard_stop = max(hard_stop, 0.05)
        if (premium - hard_stop) / premium < 0.05:
            return SizeResult(0, 0, 0, alloc, max_loss,
                              f"{lots} lots too large for the {self.cfg.max_risk_per_trade_pct:.0%} loss cap")
        return SizeResult(lots, qty, round(hard_stop, 2), alloc, max_loss)
