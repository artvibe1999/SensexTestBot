"""Trading engine: schedules, candle processing, entries, position management."""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Awaitable, Callable, Optional

import pandas as pd

from . import indicators as ind
from .brokers import FlatPosition, LiveBroker, OrderState, PaperBroker
from .charges import OrderLeg, formula_charges
from .config import IST, MARKET_CLOSE, MARKET_OPEN, Config
from .kite_service import INDEX_SYMBOL, OPT_EXCHANGE, KiteService, TokenError
from .market import BEAR, BULL, MarketContext, build_context
from .options import StrikeCandidate, choose_expiry, option_delta, select_strike
from .report import DailyReporter
from .risk import RiskManager, SizeResult
from .sheets import SheetLogger
from .store import Store
from .strategies import ALL_STRATEGIES, STRATEGY_MAP, apply_selection_overrides
from .strategies.base import CE, Signal, Strategy, sign, trend15_agrees, vwap_side_agrees
from .strategies.tuning import VERIFIED_INDEX

log = logging.getLogger(__name__)

VIX_TOKEN = 264969      # NSE:INDIA VIX
NIFTY_TOKEN = 256265    # NSE:NIFTY 50
# SENSEX heavyweights used for the advance/decline breadth feed (strategy 37).
BREADTH_STOCKS = ["HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "BHARTIARTL", "LT", "ITC", "TCS", "AXISBANK",
                  "KOTAKBANK", "SBIN", "M&M", "BAJFINANCE", "HINDUNILVR", "SUNPHARMA"]

Notifier = Callable[[str], Awaitable[None]]


@dataclass
class EntryPlan:
    """A signal that passed every pre-trade check, ready to be placed."""
    strat: Strategy
    sig: Signal
    expiry: date
    pick: StrikeCandidate
    sz: SizeResult
    lot_size: int
    fit: int = 0          # market-fit points (0-3), see Engine.market_fit
    fit_notes: str = ""


def floor5(ts: datetime) -> datetime:
    return ts.replace(minute=ts.minute - ts.minute % 5, second=0, microsecond=0)


def fmt_money(x: float) -> str:
    return f"₹{x:,.2f}"


class Engine:
    def __init__(self, cfg: Config, store: Store, kite: KiteService):
        self.cfg = cfg
        self.store = store
        self.kite = kite
        self.clock: Callable[[], datetime] = lambda: datetime.now(IST)  # replaced by the backtester
        self.risk = RiskManager(cfg, store, clock=lambda: self.clock())
        apply_selection_overrides(cfg)
        self.paper = PaperBroker(kite)
        self.live = LiveBroker(kite, cfg)
        self.notify: Notifier = self._log_notify
        self.lock = asyncio.Lock()
        self.positions: list[dict] = store.load_positions()
        self.ctx: Optional[MarketContext] = None
        self.last_candle_done: Optional[datetime] = None
        self.last_spot: float = 0.0
        self._funds_cache: tuple[float, dict] = (0.0, {})
        self._daily_cache: tuple[Optional[date], dict, float] = (None, {}, float("nan"))
        self._aux_cache: dict = {}
        self._jobs_done: set[str] = set()
        self._throttle: dict[str, datetime] = {}
        self._last_stop_check = datetime.min.replace(tzinfo=IST)
        self._last_3m: Optional[datetime] = None
        self.last_error: str = ""
        self.sheet = SheetLogger(cfg.sheets_webhook_url, cfg.sheets_secret,
                                 cfg.google_sheet_id, cfg.google_sa_json)
        self.reporter = DailyReporter(cfg, kite, store, self.risk, self.sheet)
        self._last_status: Optional[datetime] = None
        self._report_retry_at: Optional[datetime] = None
        self._outbox: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
        self._sender: Optional[asyncio.Task] = None
        self._last_reconcile = datetime.min.replace(tzinfo=IST)
        # first-boot defaults
        store.setdefault("mode", "paper")
        store.setdefault("lots_paper", "auto")
        store.setdefault("lots_live", "auto")
        store.setdefault("paused", False)
        store.setdefault("disabled", [])
        if store.get("paper_balance") is None:
            self.risk.set_paper_capital(cfg.default_paper_capital)

    # ------------------------------------------------------------ helpers
    async def _log_notify(self, text: str) -> None:
        log.info("NOTIFY %s", text)

    async def say(self, text: str) -> None:
        level = "ERROR" if text.startswith(("❌", "🛑")) else "WARN" if text.startswith("⚠️") else "INFO"
        self.sheet.log(self.mode, level, "telegram", text)
        if self._sender is not None and not self._sender.done():
            try:
                self._outbox.put_nowait(text)  # never block trading on Telegram
            except asyncio.QueueFull:
                log.warning("telegram outbox full; dropping message")
            return
        try:
            await self.notify(text)
        except Exception as exc:
            log.warning("notify failed: %s", exc)

    async def drain_outbox(self, timeout: float = 15) -> None:
        """Wait until queued Telegram messages are sent (used on shutdown)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not self._outbox.empty() and loop.time() < deadline:
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.5)  # let the message in flight finish

    async def _send_loop(self) -> None:
        while True:
            text = await self._outbox.get()
            try:
                await self.notify(text)
            except Exception as exc:
                log.warning("notify failed: %s", exc)

    async def say_throttled(self, key: str, text: str, minutes: int = 30) -> None:
        now = self.clock()
        last = self._throttle.get(key)
        if last and now - last < timedelta(minutes=minutes):
            return
        self._throttle[key] = now
        await self.say(text)

    @property
    def mode(self) -> str:
        return self.store.get("mode", "paper")

    def broker(self, mode: str) -> PaperBroker:
        return self.live if mode == "live" else self.paper

    def lots_setting(self, mode: str):
        return self.store.get(f"lots_{mode}", "auto")

    def enabled_strategies(self) -> list[Strategy]:
        disabled = set(self.store.get("disabled", []))
        return sorted((s for s in ALL_STRATEGIES if s.sid not in disabled), key=self.strategy_rank)

    async def live_funds(self, max_age: float = 30) -> dict:
        ts, data = self._funds_cache
        now = datetime.now(IST).timestamp()
        if data and now - ts < max_age:
            return data
        data = await asyncio.to_thread(self.kite.funds)
        self._funds_cache = (now, data)
        return data

    async def capital_info(self, mode: str) -> tuple[float, float]:
        """(capital used for % limits, cash available for new premium)."""
        if mode == "live":
            f = await self.live_funds()
            self.risk.update_live_peak(f["net"])
            return f["net"], f["available"]
        bal = self.risk.paper_balance()
        used = sum(p["entry_price"] * p["qty"] for p in self.positions if p["mode"] == "paper")
        return bal, bal - used

    def unrealized(self, mode: str) -> float:
        return sum((p.get("last_ltp", p["entry_price"]) - p["entry_price"]) * p["qty"] + p.get("realized_gross", 0.0)
                   for p in self.positions if p["mode"] == mode)

    def _persist(self, pos: dict) -> None:
        self.store.save_position(pos["id"], pos["mode"], pos)

    # ------------------------------------------------------------ main loop
    async def run(self) -> None:
        self._sender = asyncio.create_task(self._send_loop())
        await self.startup()
        while True:
            try:
                await self.tick(datetime.now(IST))
            except TokenError as exc:
                await self.say_throttled("token", f"⚠️ Kite session expired/invalid ({exc}). Use /login to re-authenticate.", 60)
            except Exception as exc:
                self.last_error = f"{datetime.now(IST):%H:%M:%S} {exc}"
                log.exception("tick failed")
                await self.say_throttled("tick-error", f"⚠️ Engine error: {exc}", 15)
            await asyncio.sleep(self.cfg.poll_seconds)

    async def startup(self) -> None:
        ok = await asyncio.to_thread(self.kite.load_saved_token)
        if ok:
            await asyncio.to_thread(self.kite.refresh_instruments)
            await self.say(f"✅ SENSEX PRO bot started. Kite user {self.kite.user.get('user_id', '')}. "
                           f"Mode: {self.mode.upper()}. /help for commands.")
        else:
            await self.say("🤖 SENSEX PRO bot started but Kite is not logged in.\n" + self.login_message())
        if self.positions:
            await self.say(f"♻️ Restored {len(self.positions)} open position(s) from disk.")
        self.sheet.status(self.mode, "startup", self.status_text())

    def login_message(self) -> str:
        return f"🔑 Login to Zerodha: {self.kite.login_url()}\nAfter login you'll be redirected back automatically " \
               f"(or send /token <request_token>)."

    async def on_login(self) -> None:
        await asyncio.to_thread(self.kite.refresh_instruments, True)
        self._funds_cache = (0.0, {})
        self.sheet.status(self.mode, "kite login", f"user {self.kite.user.get('user_id', '')}")
        await self.say(f"✅ Kite login successful: {self.kite.user.get('user_name', '')} "
                       f"({self.kite.user.get('user_id', '')}).")

    def _job_once(self, name: str, now: datetime) -> bool:
        key = f"{name}:{now.date()}"
        if key in self._jobs_done:
            return False
        self._jobs_done.add(key)
        return True

    async def tick(self, now: datetime) -> None:
        t = now.time()
        weekday = now.weekday() < 5

        if weekday and t >= self.cfg.login_prompt_time and self._job_once("login-check", now):
            ok = await asyncio.to_thread(self.kite.load_saved_token)
            if not ok:
                await self.say("🌅 Good morning. Daily Kite login needed.\n" + self.login_message())
            else:
                await asyncio.to_thread(self.kite.refresh_instruments, True)

        if weekday and t >= self.cfg.summary_time and self._job_once("summary", now):
            await self.say(self.day_summary(now))

        if self._last_status is None or now - self._last_status >= timedelta(minutes=self.cfg.status_interval_min):
            self._last_status = now
            self.sheet.status(self.mode, "heartbeat", self.status_text())

        if weekday and t >= self.cfg.report_time and not self.store.get(f"report_done_{now.date()}") \
                and (self._report_retry_at is None or now >= self._report_retry_at):
            await self.daily_report(now)

        if not self.kite.ready:
            return
        if not (weekday and MARKET_OPEN <= t <= MARKET_CLOSE):
            return

        async with self.lock:
            await asyncio.to_thread(self.kite.refresh_instruments)
            await self.monitor(now)
            boundary = floor5(now)
            if (self.last_candle_done is None or boundary > self.last_candle_done) and \
                    now >= boundary + timedelta(seconds=self.cfg.candle_delay_seconds) and boundary.time() > MARKET_OPEN:
                await self.on_candle_close(now, boundary)
            if any(STRATEGY_MAP.get(p["strategy"]) and STRATEGY_MAP[p["strategy"]].uses_3min for p in self.positions):
                b3 = now.replace(minute=now.minute - now.minute % 3, second=0, microsecond=0)
                if (self._last_3m is None or b3 > self._last_3m) and now >= b3 + timedelta(seconds=4):
                    self._last_3m = b3
                    await self.update_3min_trails(now)

    # ------------------------------------------------------------ candles
    async def daily_info(self, now: datetime) -> tuple[dict, float]:
        day, prev, adx = self._daily_cache
        if day == now.date() and prev:
            return prev, adx
        d = await asyncio.to_thread(self.kite.daily_candles, now, 90)
        d = d[d.index.date < now.date()]
        if d.empty:
            raise RuntimeError("no daily candles")
        last = d.iloc[-1]
        prev = {"open": float(last["open"]), "high": float(last["high"]), "low": float(last["low"]),
                "close": float(last["close"]), "date": str(d.index[-1].date())}
        adx_v = float(ind.adx(d, 14)["adx"].iloc[-1]) if len(d) > 20 else float("nan")
        self._daily_cache = (now.date(), prev, adx_v)
        return prev, adx_v

    async def build_ctx(self, now: datetime) -> Optional[MarketContext]:
        df = await asyncio.to_thread(self.kite.index_candles, now, "5minute", 8)
        if df.empty or df.index[-1].date() != now.date():
            return None
        prev, adx_v = await self.daily_info(now)
        exps = self.kite.expiries()
        nearest = exps[0] if exps else None
        aux = await self.aux_feeds(now, df, exps)
        return build_context(df, now, prev, adx_v, nearest, aux)

    def _needs(self) -> set[str]:
        needs = {n for s in self.enabled_strategies() for n in s.needs}
        if any(s.tune.get("noise_k") is not None for s in self.enabled_strategies()):
            needs.add("noise")
        for p in self.positions:
            s = STRATEGY_MAP.get(p["strategy"])
            if s:
                needs |= set(s.needs)
        return needs

    async def aux_feeds(self, now: datetime, df, exps) -> dict:
        """Extra market feeds for strategies that declare `needs` (fetched only then)."""
        needs, aux = self._needs(), {}
        if not needs:
            return aux
        day0 = datetime.combine(now.date(), time(9, 15), tzinfo=IST)

        def closed5(frame):
            return frame[frame.index + timedelta(minutes=5) <= now] if not frame.empty else frame

        async def feed(name, fn):
            try:
                aux[name] = await fn()
            except TokenError:
                raise
            except Exception as exc:
                log.warning("aux feed %s unavailable: %s", name, exc)

        async def vix():
            v = await asyncio.to_thread(self.kite.historical, VIX_TOKEN, day0, now, "5minute")
            return closed5(v)["close"] if not v.empty else None

        async def nifty():
            n = await asyncio.to_thread(self.kite.historical, NIFTY_TOKEN, day0, now, "5minute")
            return closed5(n)[["open", "high", "low", "close"]] if not n.empty else None

        async def first_min():
            fm = self._aux_cache.get(("first_min", now.date()))
            if fm is None and now.time() >= time(9, 16, 5):
                m = await asyncio.to_thread(self.kite.historical, self.kite.index_token, day0,
                                            day0 + timedelta(minutes=2), "minute")
                if not m.empty:
                    fm = m.iloc[0]
                    self._aux_cache[("first_min", now.date())] = fm
            return fm

        async def daily():
            d = self._aux_cache.get(("daily", now.date()))
            if d is None:   # completed sessions only: fetch once per day
                d = await asyncio.to_thread(self.kite.daily_candles, now, 30)
                d = d[d.index.date < now.date()]
                if not d.empty:
                    self._aux_cache[("daily", now.date())] = d
            return d

        async def noise():
            sig = self._aux_cache.get(("noise", now.date()))
            if sig is None:
                from .strategies.catalog import noise_sigma
                hist = await asyncio.to_thread(self.kite.index_candles, now, "5minute", 30)
                sig = noise_sigma(hist, now.date())
                if sig is not None:
                    self._aux_cache[("noise", now.date())] = sig
            return sig

        async def breadth():
            keys = [f"NSE:{s}" for s in BREADTH_STOCKS]
            q = await asyncio.to_thread(self.kite.quote, keys)
            adv = sum(1 for k in keys if q.get(k) and q[k]["last_price"] > (q[k].get("ohlc") or {}).get("close", 0) > 0)
            dec = sum(1 for k in keys if q.get(k) and 0 < q[k]["last_price"] < (q[k].get("ohlc") or {}).get("close", 0))
            series = self._aux_cache.setdefault(("breadth", now.date()), {})
            series[df.index[-1]] = adv / max(dec, 1)
            return pd.Series(series).sort_index()

        async def oi():
            spot = float(df["close"].iloc[-1])
            rows = self.kite.chain(exps[0], spot, 15)
            q = await asyncio.to_thread(self.kite.quote, [f"{OPT_EXCHANGE}:{r['tradingsymbol']}" for r in rows])
            out = {"expiry": exps[0], "CE": {}, "PE": {}}
            for r in rows:
                v = (q.get(f"{OPT_EXCHANGE}:{r['tradingsymbol']}") or {}).get("oi")
                if v:
                    out[r["instrument_type"]][float(r["strike"])] = float(v)
            return out

        for name, fn in (("vix", vix), ("nifty", nifty), ("first_min", first_min), ("daily", daily),
                         ("noise", noise), ("breadth", breadth), ("oi", oi)):
            if name in needs and (name != "oi" or exps):
                await feed(name, fn)
        # drop caches of earlier days
        for k in [k for k in self._aux_cache if k[1] != now.date()]:
            del self._aux_cache[k]
        return aux

    async def on_candle_close(self, now: datetime, boundary: datetime) -> None:
        ctx = await self.build_ctx(now)
        expected_last = boundary - timedelta(minutes=5)
        if ctx is None:
            if now - boundary > timedelta(seconds=60):
                self.last_candle_done = boundary  # holiday / no data; don't spin
            return
        if ctx.df.index[-1] < expected_last and now - boundary < timedelta(seconds=40):
            return  # candle not published yet; retry next tick
        self.last_candle_done = boundary
        prev_regime = self.ctx.regime if self.ctx else None
        self.ctx = ctx
        if prev_regime and prev_regime != ctx.regime:
            await self.say_throttled(f"regime-{ctx.regime}",
                                     f"🧭 Regime: {prev_regime} → {ctx.regime}  ({ctx.regime_detail})", 20)
        if float(ctx.today["volume"].sum()) <= 0:
            await self.say_throttled("novol", "⚠️ No SENSEX futures volume — volume-confirmed strategies will not trigger.", 240)

        for pos in list(self.positions):
            await self.manage_on_close(ctx, pos, now)
        await self.try_entries(ctx, now)

    async def update_3min_trails(self, now: datetime) -> None:
        df3 = await asyncio.to_thread(self.kite.index_candles, now, "3minute", 1)
        if df3.empty:
            return
        last = df3.iloc[-1]
        for pos in self.positions:
            s = STRATEGY_MAP.get(pos["strategy"])
            if not s or not s.uses_3min:
                continue
            if pos.get("trail_active"):
                lvl = float(last["low"] if pos["direction"] == CE else last["high"])
                self._ratchet(pos, lvl)
                self._persist(pos)

    # ------------------------------------------------------------ entries
    def _setups(self, day: str) -> dict:
        return self.store.get(f"setups_{day}", {}) or {}

    def _reentry_ok(self, strat: Strategy, sig: Signal, day: str) -> bool:
        used = self._setups(day).get(strat.sid, [])
        if not used:
            return True
        if len(used) >= strat.max_entries:
            return False
        if strat.reentry == "no":
            return False
        if strat.reentry == "setup":
            return sig.setup_key not in used
        return True

    async def try_entries(self, ctx: MarketContext, now: datetime) -> None:
        mode = self.mode
        if self.store.get("paused", False):
            return
        t = ctx.close_time
        if t < self.cfg.entry_start or t > self.cfg.entry_cutoff or now.time() >= self.cfg.squareoff_time:
            return
        if len([p for p in self.positions if p["mode"] == mode]) >= self.cfg.max_open_positions:
            return
        capital, available = await self.capital_info(mode)
        ok, why = self.risk.can_open(mode, capital, now, self.unrealized(mode))
        if not ok:
            await self.say_throttled(f"block-{why}", f"⛔ New entries blocked: {why}", 120)
            return
        day = now.date().isoformat()
        signals: list[tuple[Strategy, Signal]] = []
        for strat in self.enabled_strategies():
            if not strat.in_window(ctx):
                continue
            try:
                sig = strat.entry(ctx)
                sig = strat.apply_tuning(ctx, sig) if sig is not None else None
            except Exception as exc:
                log.exception("strategy %s failed", strat.sid)
                await self.say_throttled(f"strat-{strat.sid}", f"⚠️ {strat.sid} error: {exc}", 120)
                continue
            if sig is None:
                continue
            if not strat.regime_ok(ctx, sig.direction, strat.category):
                log.info("%s %s blocked by regime %s", strat.sid, sig.direction, ctx.regime)
                continue
            if not self._reentry_ok(strat, sig, day):
                continue
            signals.append((strat, sig))
        if not signals:
            return
        # Rank every signal (verified set first, then market fit, then priority), then run the
        # full pre-trade check (expiry, strike in the strategy's delta / premium band with an
        # acceptable spread, configured lots within the available margin, per-trade loss cap)
        # in that order and place the first that passes. A failed check or an order that
        # provably did not fill falls through to the next candidate.
        ranked = []
        for strat, sig in signals:
            fit, fit_notes = self.market_fit(ctx, sig.direction)
            group, prio = self.strategy_rank(strat)
            ranked.append(((group, -fit, prio), strat, sig, fit, fit_notes))
        ranked.sort(key=lambda r: r[0])
        chains: dict = {}
        notes: list[str] = []
        for i, (_, strat, sig, fit, fit_notes) in enumerate(ranked):
            try:
                plan, why = await self.plan_entry(ctx, now, mode, strat, sig, capital, available, chains)
            except TokenError:
                raise
            except Exception as exc:
                log.exception("pre-trade check %s failed", strat.sid)
                plan, why = None, f"pre-trade check error: {exc}"
            if plan is None:
                notes.append(f"{strat.sid} {sig.direction}: {why}")
                await self.say_throttled(f"skip-{strat.sid}", f"⏭️ {strat.sid} {sig.direction} signal skipped: {why}", 30)
                continue
            plan.fit, plan.fit_notes = fit, fit_notes
            later = [f"{s.sid} {g.direction} (fit {f}/3, not needed)" for _, s, g, f, _n in ranked[i + 1:]]
            pos, retry_ok = await self.execute_entry(ctx, now, mode, plan, capital, "; ".join(notes + later))
            if pos is not None or not retry_ok:
                return
            notes.append(f"{strat.sid} {sig.direction}: order not filled")

    def strategy_rank(self, strat: Strategy) -> tuple[int, float]:
        """Order of the enabled strategies: the verified set (strategies/tuning.py VERIFIED_ORDER)
        first in its listed order, then any other enabled strategy, e.g. one switched on with
        /enable, by its tune / class priority."""
        if strat.sid in VERIFIED_INDEX:
            return 0, float(VERIFIED_INDEX[strat.sid])
        return 1, float(strat.tune.get("priority", strat.priority))

    @staticmethod
    def market_fit(ctx: MarketContext, direction: str) -> tuple[int, str]:
        """How well the current market agrees with a trade: one point each for the regime,
        the 15-minute 9/21 EMA trend and the side of VWAP."""
        d = sign(direction)
        notes = []
        if (ctx.regime == BULL and d > 0) or (ctx.regime == BEAR and d < 0):
            notes.append("regime")
        if trend15_agrees(ctx, direction):
            notes.append("15m trend")
        if vwap_side_agrees(ctx, direction):
            notes.append("VWAP side")
        return len(notes), ", ".join(notes) or "none"

    async def _option_chain(self, ctx: MarketContext, now: datetime, expiry: date, direction: str,
                            chains: dict) -> list[StrikeCandidate]:
        """Quoted strikes around ATM for one expiry and side; one Kite quote call that also
        returns the live SENSEX price (cached per candle in `chains`)."""
        key = (expiry, direction)
        if key in chains:
            return chains[key]
        ref = self.last_spot or float(ctx.last["close"])
        rows = [r for r in self.kite.chain(expiry, ref, 12) if r["instrument_type"] == direction]
        keys = [INDEX_SYMBOL] + [f"{OPT_EXCHANGE}:{r['tradingsymbol']}" for r in rows]
        quotes = await asyncio.to_thread(self.kite.quote, keys) if rows else {}
        spot = float((quotes.get(INDEX_SYMBOL) or {}).get("last_price") or 0.0) or ref
        self.last_spot = spot
        cands: list[StrikeCandidate] = []
        for r in rows:
            q = quotes.get(f"{OPT_EXCHANGE}:{r['tradingsymbol']}")
            if not q:
                continue
            depth = q.get("depth") or {}
            bid = next((float(l["price"]) for l in depth.get("buy", []) if l.get("price", 0) > 0), 0.0)
            ask = next((float(l["price"]) for l in depth.get("sell", []) if l.get("price", 0) > 0), 0.0)
            ltp = float(q.get("last_price", 0.0))
            mid = (bid + ask) / 2 if bid and ask else ltp
            if mid <= 0:
                continue
            dlt = option_delta(mid, spot, float(r["strike"]), now, expiry, self.cfg.risk_free_rate, direction == CE)
            cands.append(StrikeCandidate(r["tradingsymbol"], int(r["instrument_token"]), float(r["strike"]),
                                         direction, expiry, int(r["lot_size"]), float(r.get("tick_size") or 0.05),
                                         ltp, bid, ask, dlt))
        chains[key] = cands
        return cands

    async def plan_entry(self, ctx: MarketContext, now: datetime, mode: str, strat: Strategy, sig: Signal,
                         capital: float, available: float, chains: Optional[dict] = None
                         ) -> tuple[Optional[EntryPlan], str]:
        """Pre-trade check for one signal in `mode`; returns (plan, "") or (None, reason)."""
        expiry = choose_expiry(self.kite.expiries(), now.date(), strat.expiry_rule, now.time())
        if expiry is None:
            return None, "no eligible expiry"
        cands = await self._option_chain(ctx, now, expiry, sig.direction, {} if chains is None else chains)
        lot_size = cands[0].lot_size if cands else self.kite.lot_size()
        lots_set = self.lots_setting(mode)
        pct = strat.capital_pct
        alloc = max(0.0, available) * self.cfg.alloc_pct * (pct / 0.10) * (0.5 if self.risk.emergency(mode, capital) else 1)
        max_aff = alloc / lot_size if lots_set == "auto" else alloc / (int(lots_set) * lot_size)
        pick, why = select_strike(cands, strat.delta_min, strat.delta_max, strat.delta_target,
                                  strat.prem_min, strat.prem_max, max_aff, self.cfg.max_spread_pct)
        if pick is None:
            return None, why
        premium = pick.entry_price
        strat_prem_stop = premium * (1 - sig.prem_sl_pct) if sig.prem_sl_pct else None
        sz = self.risk.size(mode, capital, available, premium, lot_size, pct, lots_set, strat_prem_stop)
        if sz.lots <= 0:
            return None, sz.reason
        return EntryPlan(strat, sig, expiry, pick, sz, lot_size), ""

    async def execute_entry(self, ctx: MarketContext, now: datetime, mode: str, plan: EntryPlan, capital: float,
                            others: str = "") -> tuple[Optional[dict], bool]:
        """Place the planned entry. Returns (position or None, safe to try another candidate):
        the second value is True only when the order provably left no exposure."""
        today = now.date()
        strat, sig, expiry, pick, sz, lot_size = plan.strat, plan.sig, plan.expiry, plan.pick, plan.sz, plan.lot_size
        premium = pick.entry_price
        und_stop = sig.sl_price if sig.sl_price is not None else sig.sl_close
        broker = self.broker(mode)
        try:
            fill = await asyncio.to_thread(broker.buy, pick.tradingsymbol, sz.qty, pick.tick_size)
        except TokenError:
            raise
        except Exception as exc:
            await self.say(f"❌ {mode.upper()} entry failed for {pick.tradingsymbol}: {exc}")
            # paper never leaves an order behind; a live error may have placed one
            return None, mode == "paper" or "rejected" in str(exc)
        if fill.uncertain:
            await self.say(f"⚠️ {pick.tradingsymbol} entry order {fill.order_id} is still working after a cancel "
                           f"attempt — check Kite (bot tracks {fill.qty} filled).")
        if fill.qty <= 0:
            await self.say(f"❌ {mode.upper()} entry not filled for {pick.tradingsymbol} (limit timed out).")
            return None, not fill.uncertain
        hard_stop = round(max(0.05, sz.hard_stop + (fill.price - premium)), 2)
        self.sheet.order(mode, strat.sid, "ENTRY", pick.tradingsymbol, "BUY", fill.qty, premium, fill.price,
                         f"{sig.note} | regime {ctx.regime}", now)
        pos = {
            "id": uuid.uuid4().hex[:10], "mode": mode, "strategy": strat.sid, "direction": sig.direction,
            "symbol": pick.tradingsymbol, "token": pick.instrument_token, "strike": pick.strike,
            "expiry": str(expiry), "lot_size": lot_size, "tick": pick.tick_size,
            "qty": fill.qty, "initial_qty": fill.qty, "entry_price": fill.price,
            "entry_time": now.isoformat(), "entry_candle": str(ctx.df.index[-1]),
            "underlying_entry": float(ctx.last["close"]), "sl_price": sig.sl_price, "stop_ref": und_stop,
            "target": sig.target, "book_fraction": sig.book_fraction, "booked": False,
            "prem_stop": hard_stop, "prem_target": fill.price * (1 + sig.prem_target_pct) if sig.prem_target_pct else None,
            "trail_level": None, "trail_active": False, "sl_order_id": None, "setup_key": sig.setup_key,
            "time_exit": strat.tune.get("time_exit", "15:20" if strat.tune.get("hold_close") else strat.time_exit.strftime("%H:%M")),
            "max_hold_min": int(strat.tune.get("max_hold", 330 if strat.tune.get("hold_close") else strat.max_hold_min)),
            "meta": sig.meta, "realized_gross": 0.0, "exit_value": 0.0, "exit_qty": 0, "exit_orders": 0,
            "last_ltp": fill.price, "delta": round(pick.delta, 2), "note": sig.note, "regime": ctx.regime,
            "entry_order_id": fill.order_id, "exit_legs": [],
        }
        if mode == "live":
            try:
                pos["sl_order_id"] = await asyncio.to_thread(broker.place_stop, pick.tradingsymbol, fill.qty,
                                                             hard_stop, pick.tick_size)
                self.sheet.order(mode, strat.sid, "SL ORDER", pick.tradingsymbol, "SELL", fill.qty, hard_stop, "",
                                 f"exchange stop-loss trigger {hard_stop:.2f}", now)
            except Exception as exc:
                await self.say(f"⚠️ Exchange SL order failed ({exc}); bot will manage the stop itself.")
        self.positions.append(pos)
        self._persist(pos)
        self.risk.note_entry(mode, now)
        setups = self._setups(today.isoformat())
        setups.setdefault(strat.sid, []).append(sig.setup_key or "x")
        self.store.set(f"setups_{today.isoformat()}", setups)
        tgt = f"{sig.target:.0f}" if sig.target else "-"
        stop_txt = f"{und_stop:.0f}" if und_stop is not None else "-"
        await self.say(
            f"🟢 {mode.upper()} BUY {pick.tradingsymbol} x{fill.qty} ({fill.qty // lot_size} lots) @ {fill.price:.2f}\n"
            f"Strategy: {strat.sid} – {strat.name}\nWhy: {sig.note} | Regime {ctx.regime}\n"
            f"SENSEX {ctx.last['close']:.0f} | Δ {pick.delta:.2f} | spread {pick.spread_pct:.2%}\n"
            f"Underlying SL {stop_txt} · Target {tgt} · Premium stop {hard_stop:.2f}\n"
            f"Capital {fmt_money(capital)} · Max loss {fmt_money(sz.max_loss)}\n"
            f"Market fit {plan.fit}/3 ({plan.fit_notes}) · {sz.lots} lots within margin {fmt_money(sz.alloc)}"
            + (f"\nAlso checked: {others}" if others else "")
        )
        return pos, False

    # ------------------------------------------------------------ position management
    def _ratchet(self, pos: dict, level: Optional[float]) -> None:
        if level is None or (isinstance(level, float) and math.isnan(level)):
            return
        old = pos.get("trail_level")
        if old is None:
            pos["trail_level"] = level
        elif pos["direction"] == CE:
            pos["trail_level"] = max(old, level)
        else:
            pos["trail_level"] = min(old, level)

    def _r_points(self, pos: dict) -> float:
        ref = pos.get("stop_ref")
        return abs(pos["underlying_entry"] - ref) if ref is not None else 0.0

    async def manage_on_close(self, ctx: MarketContext, pos: dict, now: datetime) -> None:
        strat = STRATEGY_MAP.get(pos["strategy"])
        if strat is None:
            return
        c = ctx.last
        try:
            reason = strat.exit_on_close(ctx, pos)
        except Exception as exc:
            log.exception("exit_on_close %s", strat.sid)
            reason = None
            await self.say_throttled(f"exit-err-{strat.sid}", f"⚠️ {strat.sid} exit check error: {exc}", 60)
        if reason:
            await self.close(pos, reason)
            return
        # trailing stop
        if strat.trail_kind == "none":
            return
        r = self._r_points(pos)
        favour = sign(pos["direction"]) * (float(c["close"]) - pos["underlying_entry"])
        if not pos.get("trail_active") and (pos.get("booked") or (r > 0 and favour >= r)):
            pos["trail_active"] = True
        if not pos.get("trail_active"):
            return
        level = strat.trail_level(ctx, pos)
        if strat.uses_3min:
            self._persist(pos)
            return  # 3-min trail updated separately
        if strat.trail_kind == "close":
            if level is not None and sign(pos["direction"]) * (float(c["close"]) - level) < 0:
                await self.close(pos, f"trailing stop (close across {level:.0f})")
                return
            self._ratchet(pos, level)
        else:
            self._ratchet(pos, level)
        self._persist(pos)

    async def monitor(self, now: datetime) -> None:
        if not self.positions:
            try:
                q = await asyncio.to_thread(self.kite.quote, [INDEX_SYMBOL])
                self.last_spot = float(q[INDEX_SYMBOL]["last_price"])
            except TokenError:
                raise
            except Exception:
                pass
            return
        keys = [INDEX_SYMBOL] + [f"{OPT_EXCHANGE}:{p['symbol']}" for p in self.positions]
        quotes = await asyncio.to_thread(self.kite.quote, keys)
        spot = float(quotes.get(INDEX_SYMBOL, {}).get("last_price", self.last_spot) or self.last_spot)
        self.last_spot = spot
        spot_ok = spot > 0  # never evaluate underlying stops/targets on a missing quote
        check_stops = (now - self._last_stop_check).total_seconds() >= 8
        if check_stops:
            self._last_stop_check = now

        for p in self.positions:
            q = quotes.get(f"{OPT_EXCHANGE}:{p['symbol']}", {})
            p["last_ltp"] = float(q.get("last_price", p.get("last_ltp", p["entry_price"])))
        for mode in ("paper", "live"):
            if not any(p["mode"] == mode for p in self.positions):
                continue
            try:
                capital, _ = await self.capital_info(mode)
            except TokenError:
                raise
            except Exception:
                continue
            if self.risk.daily_loss_breached(mode, capital, now, self.unrealized(mode)):
                for p in [p for p in self.positions if p["mode"] == mode]:
                    await self.close(p, "daily loss limit hit")
                await self.say_throttled(f"dailyloss-{mode}",
                                         f"🛑 {mode.upper()} daily loss limit reached — trading suspended for today.", 60)
                continue

        if any(p["mode"] == "live" for p in self.positions) and (now - self._last_reconcile).total_seconds() >= 30:
            self._last_reconcile = now
            await self.reconcile_live()

        for pos in list(self.positions):
            ltp = pos["last_ltp"]
            d = sign(pos["direction"])
            if pos.get("pending_exit"):
                if now >= datetime.fromisoformat(pos.get("pending_exit_at") or now.isoformat()):
                    await self.close(pos, pos["pending_exit"])
                continue
            if pos["mode"] == "live" and pos.get("sl_order_id") and check_stops:
                fill = await asyncio.to_thread(self.live.stop_filled, pos["sl_order_id"])
                if fill:
                    await self._finalize_exit(pos, fill.price, fill.qty, "exchange SL order hit")
                    continue
            exchange_sl = pos["mode"] == "live" and pos.get("sl_order_id")
            if ltp > 0 and ltp <= pos["prem_stop"] and not exchange_sl:
                await self.close(pos, f"premium stop {pos['prem_stop']:.2f}", floor_price=pos["prem_stop"])
                continue
            if exchange_sl and 0 < ltp <= pos["prem_stop"] * 0.97:
                # SL-limit sits 5% under its trigger and can be skipped in a fast fall: exit ourselves.
                await self.close(pos, f"premium stop {pos['prem_stop']:.2f} (exchange SL not filled, LTP {ltp:.2f})")
                continue
            if not spot_ok:
                continue
            if pos.get("sl_price") is not None and d * (spot - pos["sl_price"]) <= 0:
                await self.close(pos, f"underlying stop {pos['sl_price']:.0f} (SENSEX {spot:.0f})")
                continue
            strat = STRATEGY_MAP.get(pos["strategy"])
            if strat and strat.trail_kind == "price" and pos.get("trail_active") and pos.get("trail_level") is not None \
                    and d * (spot - pos["trail_level"]) <= 0:
                await self.close(pos, f"trailing stop {pos['trail_level']:.0f} (SENSEX {spot:.0f})")
                continue
            hit_target = (pos.get("target") is not None and d * (spot - pos["target"]) >= 0) or \
                         (pos.get("prem_target") is not None and ltp >= pos["prem_target"])
            if hit_target and not pos.get("booked"):
                lots = pos["qty"] // pos["lot_size"]
                book_lots = math.floor(lots * pos["book_fraction"]) if pos["book_fraction"] < 1 else lots
                if pos["book_fraction"] < 1 and 0 < book_lots < lots:
                    before = pos["qty"]
                    await self.close(pos, "target – partial profit booking", qty=book_lots * pos["lot_size"])
                    if pos in self.positions and pos["qty"] < before:
                        pos["booked"] = True
                        pos["trail_active"] = True
                        self._persist(pos)
                else:
                    await self.close(pos, "target reached")
                continue
            hhmm = time.fromisoformat(pos["time_exit"])
            entry_t = datetime.fromisoformat(pos["entry_time"])
            if now.time() >= min(hhmm, self.cfg.squareoff_time):
                await self.close(pos, "time exit" if now.time() < self.cfg.squareoff_time else "intraday square-off")
                continue
            if now - entry_t >= timedelta(minutes=pos["max_hold_min"]):
                await self.close(pos, f"max holding {pos['max_hold_min']} min")
                continue

    async def close(self, pos: dict, reason: str, qty: Optional[int] = None, floor_price: Optional[float] = None) -> None:
        if pos not in self.positions:
            return
        qty = min(qty or pos["qty"], pos["qty"])
        full = qty >= pos["qty"]
        broker = self.broker(pos["mode"])
        keep: tuple[str, ...] = ()
        if pos["mode"] == "live" and pos.get("sl_order_id"):
            if full:
                st: OrderState = await asyncio.to_thread(broker.cancel_stop, pos["sl_order_id"])
                if st.status == "COMPLETE":
                    await self._finalize_exit(pos, st.avg, st.filled, "exchange SL order hit")
                    return
                if not st.terminal:
                    # Cancel did not go through: selling now could double-sell. Retry shortly.
                    self._defer_exit(pos, reason)
                    await self.say_throttled(f"slcancel-{pos['id']}", f"⚠️ Could not cancel SL order for "
                                             f"{pos['symbol']} (status {st.status}); retrying exit.", 5)
                    return
                pos["sl_order_id"] = None
                if st.filled > 0:  # SL partially executed before the cancel
                    self._apply_partial(pos, st.avg, st.filled, "exchange SL partial fill")
                    if pos["qty"] <= 0:
                        await self._finalize_exit(pos, st.avg, 0, "exchange SL order hit")
                        return
                    qty = pos["qty"]
            else:
                keep = (pos["sl_order_id"],)
        try:
            fill = await asyncio.to_thread(broker.sell, pos["symbol"], qty, pos["tick"], floor_price, keep)
        except FlatPosition:
            await self.adopt_external_close(pos, "Kite shows the position already closed")
            return
        except Exception as exc:
            if full:
                self._defer_exit(pos, reason)
            await self.say_throttled(f"exitfail-{pos['id']}",
                                     f"❌ EXIT FAILED for {pos['symbol']} ({reason}): {exc}. Retrying; check Kite!", 5)
            return
        pos.pop("pending_exit", None)
        if full or fill.qty >= pos["qty"]:
            await self._finalize_exit(pos, fill.price, fill.qty, reason)
            return
        self._apply_partial(pos, fill.price, fill.qty, reason)
        if pos["mode"] == "live" and pos.get("sl_order_id"):
            try:
                await asyncio.to_thread(broker.modify_stop, pos["sl_order_id"], pos["qty"], pos["prem_stop"], pos["tick"])
            except Exception as exc:
                await self.say(f"⚠️ Could not resize SL order: {exc}")
        self._persist(pos)
        await self.say(f"🟡 {pos['mode'].upper()} PARTIAL EXIT {pos['symbol']} x{fill.qty} @ {fill.price:.2f} "
                       f"({reason}). Remaining {pos['qty']}.")

    def _defer_exit(self, pos: dict, reason: str, seconds: int = 15) -> None:
        pos["pending_exit"] = reason
        pos["pending_exit_at"] = (self.clock() + timedelta(seconds=seconds)).isoformat()
        self._persist(pos)

    def _apply_partial(self, pos: dict, price: float, qty: int, reason: str) -> None:
        pos["qty"] -= qty
        pos["realized_gross"] += (price - pos["entry_price"]) * qty
        pos["exit_value"] += price * qty
        pos["exit_qty"] += qty
        pos["exit_orders"] += 1
        pos.setdefault("exit_legs", []).append([price, qty])
        self.sheet.order(pos["mode"], pos["strategy"], "PARTIAL EXIT", pos["symbol"], "SELL", qty,
                         pos.get("last_ltp"), price, reason)
        self._persist(pos)

    async def reconcile_live(self) -> None:
        """Detect live positions closed outside the bot (manual exit, broker MIS square-off)."""
        try:
            net = await asyncio.to_thread(self.kite.positions)
        except TokenError:
            raise
        except Exception as exc:
            log.warning("live reconcile skipped: %s", exc)
            return
        held: dict[str, int] = {}
        for p in net.get("net", []):
            if p.get("exchange") == OPT_EXCHANGE:
                held[p["tradingsymbol"]] = held.get(p["tradingsymbol"], 0) + int(p.get("quantity") or 0)
        for pos in [p for p in self.positions if p["mode"] == "live"]:
            qty = held.get(pos["symbol"], 0)
            if qty <= 0 and not pos.get("pending_exit"):
                if await asyncio.to_thread(self.live.stop_filled, pos.get("sl_order_id")):
                    continue  # the SL fill path will book it
                await self.adopt_external_close(pos, "closed outside the bot (Kite position is flat)")
            elif qty != pos["qty"]:
                extra = " (extra quantity is NOT managed by the bot: no stop, no exit)" if qty > pos["qty"] else ""
                await self.say_throttled(f"mismatch-{pos['id']}", f"⚠️ {pos['symbol']}: bot tracks {pos['qty']} but "
                                         f"Kite holds {qty}{extra}. Check the account.", 30)

    async def adopt_external_close(self, pos: dict, reason: str) -> None:
        """Book a position that is already flat at Zerodha, priced from today's SELL fills."""
        price = pos.get("last_ltp") or pos["entry_price"]
        try:
            orders = await asyncio.to_thread(self.kite.orders)
            sells = [o for o in orders if o.get("tradingsymbol") == pos["symbol"] and o.get("status") == "COMPLETE"
                     and o.get("transaction_type") == "SELL" and str(o.get("order_timestamp")) >= pos["entry_time"][:19].replace("T", " ")]
            q = sum(int(o["filled_quantity"]) for o in sells)
            if q:
                price = sum(int(o["filled_quantity"]) * float(o["average_price"]) for o in sells) / q
        except Exception as exc:
            log.warning("pricing external close failed: %s", exc)
        if pos.get("sl_order_id"):
            await asyncio.to_thread(self.live.cancel_stop, pos["sl_order_id"])
        pos.pop("pending_exit", None)
        await self._finalize_exit(pos, round(price, 2), pos["qty"], reason)

    async def _finalize_exit(self, pos: dict, price: float, qty: int, reason: str) -> None:
        pos["exit_value"] += price * qty
        pos["exit_qty"] += qty
        pos["exit_orders"] += 1
        if qty > 0:
            pos.setdefault("exit_legs", []).append([price, qty])
            self.sheet.order(pos["mode"], pos["strategy"], "EXIT", pos["symbol"], "SELL", qty,
                             pos.get("last_ltp"), price, reason)
        total_qty = pos["exit_qty"]
        avg_exit = pos["exit_value"] / total_qty if total_qty else price
        gross = (avg_exit - pos["entry_price"]) * total_qty
        legs = [OrderLeg("b", pos["symbol"], "BUY", total_qty, pos["entry_price"])] + \
            [OrderLeg(f"s{i}", pos["symbol"], "SELL", int(q), float(px)) for i, (px, q) in enumerate(pos["exit_legs"])]
        charges = sum(formula_charges(l) for l in legs)
        net = gross - charges
        now = self.clock()
        self.store.record_trade({
            "position_id": pos["id"], "mode": pos["mode"], "strategy": pos["strategy"], "symbol": pos["symbol"],
            "option_type": pos["direction"], "qty": total_qty, "entry_price": pos["entry_price"],
            "exit_price": round(avg_exit, 2), "gross_pnl": round(gross, 2), "charges": round(charges, 2),
            "net_pnl": round(net, 2), "entry_time": pos["entry_time"], "exit_time": now.isoformat(),
            "exit_reason": reason, "trade_day": now.date().isoformat(), "legs": pos["exit_legs"],
        })
        self.positions.remove(pos)
        self.store.delete_position(pos["id"])
        was_cooling = self.store.get(f"{pos['mode']}_cooldown_until")
        self.risk.on_trade_closed(pos["mode"], net)
        started_cooloff = self.store.get(f"{pos['mode']}_cooldown_until") != was_cooling
        emoji = "✅" if net >= 0 else "🔴"
        bal = f"\nPaper balance: {fmt_money(self.risk.paper_balance())}" if pos["mode"] == "paper" else ""
        await self.say(
            f"{emoji} {pos['mode'].upper()} EXIT {pos['symbol']} x{qty} @ {price:.2f} — {reason}\n"
            f"Entry {pos['entry_price']:.2f} → avg exit {avg_exit:.2f} | Gross {fmt_money(gross)} | "
            f"Charges≈ {fmt_money(charges)} | Net≈ {fmt_money(net)}{bal}"
            + (f"\n⚠️ {self.cfg.max_consecutive_losses} straight losses → {self.cfg.cooloff_hours:.0f}h cool-off."
               if started_cooloff else "")
        )

    async def squareoff_all(self, reason: str = "manual square-off") -> int:
        async with self.lock:
            n = 0
            for p in list(self.positions):
                await self.close(p, reason)
                n += 1
            return n

    # ------------------------------------------------------------ reporting
    def status_text(self) -> str:
        now = self.clock()
        st = self.risk.day_stats(self.mode, now)
        regime = self.ctx.regime if self.ctx else "-"
        return (f"kite={'ok' if self.kite.ready else 'LOGGED OUT'} | mode={self.mode} | paused={self.store.get('paused')} | "
                f"lots paper={self.lots_setting('paper')} live={self.lots_setting('live')} | "
                f"paper_balance={self.risk.paper_balance():,.2f} | regime={regime} | spot={self.last_spot:.1f} | "
                f"open_positions={len(self.positions)} | entries_today={st['entries']} | "
                f"realized_today={st['realized']:,.2f} | unrealized={self.unrealized(self.mode):,.2f}"
                + (f" | last_error={self.last_error}" if self.last_error else "")
                + (f" | sheet_error={self.sheet.last_error}" if self.sheet.last_error else ""))

    async def daily_report(self, now: datetime) -> Optional[str]:
        """Reconcile today's live + paper trades with Zerodha charges and publish."""
        try:
            async with self.lock:
                text = await asyncio.to_thread(self.reporter.run, now.date())
        except Exception as exc:
            log.exception("daily report failed")
            self._report_retry_at = now + timedelta(minutes=3)
            await self.say_throttled("report-fail", f"⚠️ Daily report failed: {exc} (retrying)", 30)
            return None
        self.store.set(f"report_done_{now.date()}", datetime.now(IST).isoformat(timespec="seconds"))
        self._report_retry_at = None
        self.sheet.status(self.mode, "daily report", text.replace("\n", " | "))
        await self.say(text)
        return text

    def day_summary(self, now: datetime) -> str:
        lines = [f"📊 Daily summary {now:%d %b %Y}"]
        for mode in ("paper", "live"):
            st = self.risk.day_stats(mode, now)
            if st["closed"] == 0 and mode != self.mode:
                continue
            lines.append(f"{mode.upper()}: {st['closed']} trades · net {fmt_money(st['realized'])} · "
                         f"week {fmt_money(st['week_realized'])}")
            for t in self.store.trades(mode, since_day=now.date().isoformat()):
                lines.append(f"  {t['strategy']} {t['symbol']} {t['net_pnl']:+,.0f} ({t['exit_reason']})")
        lines.append(f"Paper balance: {fmt_money(self.risk.paper_balance())}")
        return "\n".join(lines)
