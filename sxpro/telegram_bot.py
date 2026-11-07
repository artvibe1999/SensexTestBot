"""Telegram notifications + command interface (only the configured chat is obeyed)."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from .config import IST, Config
from .engine import Engine, fmt_money
from .strategies import ALL_STRATEGIES, STRATEGY_MAP

log = logging.getLogger(__name__)

HELP = """SENSEX PRO bot commands

Status
/status – mode, capital, risk state, open positions
/positions – open positions with live P&L
/trades [paper|live] – today's closed trades
/pnl – daily summary
/regime – current market regime
/funds – live Zerodha funds
/report – run the reconciliation report now (Zerodha charges, sheet)

Control
/mode paper | /mode live – switch trading mode (live asks /confirmlive)
/lots paper <n|auto> – lots per paper trade
/lots live <n|auto> – lots per live trade
/capital <amount> – set paper trading capital (resets paper balance)
/pause | /resume – stop / allow new entries
/squareoff – close all open positions now
/ids – all strategy IDs with ✅ enabled / ⛔ disabled
/strategies – strategies with full details
/enable <ID|all>; /disable <ID|all> – e.g. /enable VWAP_03 (short ID works)

Kite login
/login – get the Zerodha login link
/token <request_token or redirect URL> – manual login fallback"""

MAX_FIXED_LOTS = 50  # SENSEX freeze quantity (1000) / lot size (20)

MENU = [
    ("status", "Mode, capital, risk gate, positions"), ("ids", "All strategy IDs (enabled/disabled)"),
    ("strategies", "Strategies with details"), ("enable", "Enable a strategy: /enable <ID|all>"),
    ("disable", "Disable a strategy: /disable <ID|all>"), ("positions", "Open positions"),
    ("trades", "Today's trades: /trades [paper|live]"), ("pnl", "Daily summary"), ("regime", "Market regime"),
    ("funds", "Live Zerodha funds"), ("mode", "Switch mode: /mode paper|live"), ("lots", "/lots paper|live <n|auto>"),
    ("capital", "Paper capital: /capital <amount>"), ("pause", "Pause new entries"), ("resume", "Resume entries"),
    ("squareoff", "Close all positions now"), ("report", "Run the reconciliation report"),
    ("login", "Zerodha login link"), ("help", "All commands"),
]


def ids_text(disabled: set[str]) -> str:
    """Compact list of every strategy ID with its on/off state (for /ids)."""
    on = [s for s in ALL_STRATEGIES if s.sid not in disabled]
    lines = [f"🗂 Strategy IDs — {len(on)}/{len(ALL_STRATEGIES)} enabled"]
    lines += [f"{'✅' if s.sid not in disabled else '⛔'} {s.sid} — {s.name}" for s in ALL_STRATEGIES]
    lines.append("\nUse the full ID or the short part, e.g. /disable SENSEX_GAP_07 or /enable GAP_07")
    return "\n".join(lines)


class TelegramController:
    def __init__(self, cfg: Config, engine: Engine):
        self.cfg = cfg
        self.engine = engine
        self.chat_id = int(cfg.telegram_chat_id)
        self.app = Application.builder().token(cfg.telegram_token).build()
        self._live_confirm_until: datetime | None = None
        only_me = filters.Chat(chat_id=self.chat_id)
        handlers = {
            "start": self.cmd_help, "help": self.cmd_help, "status": self.cmd_status,
            "positions": self.cmd_positions, "trades": self.cmd_trades, "pnl": self.cmd_pnl,
            "regime": self.cmd_regime, "funds": self.cmd_funds, "mode": self.cmd_mode,
            "confirmlive": self.cmd_confirm_live, "lots": self.cmd_lots, "capital": self.cmd_capital,
            "pause": self.cmd_pause, "resume": self.cmd_resume, "squareoff": self.cmd_squareoff,
            "strategies": self.cmd_strategies, "ids": self.cmd_ids,
            "enable": self.cmd_enable, "disable": self.cmd_disable,
            "login": self.cmd_login, "token": self.cmd_token, "report": self.cmd_report,
        }
        for name, fn in handlers.items():
            self.app.add_handler(CommandHandler(name, fn, filters=only_me))
        engine.notify = self.send

    async def start(self) -> None:
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        try:  # show the commands in Telegram's "/" menu
            await self.app.bot.set_my_commands([BotCommand(c, d) for c, d in MENU])
        except Exception as exc:
            log.warning("set_my_commands failed: %s", exc)

    async def stop(self) -> None:
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    async def send(self, text: str) -> None:
        for i in range(0, len(text), 3900):
            for attempt in range(3):
                try:
                    await self.app.bot.send_message(self.chat_id, text[i:i + 3900], disable_web_page_preview=True)
                    break
                except Exception as exc:
                    log.warning("telegram send failed (%s), retry %d", exc, attempt)
                    await asyncio.sleep(2 * (attempt + 1))

    async def reply(self, update: Update, text: str) -> None:
        await self.send(text)

    def _event(self, event: str, details: str) -> None:
        self.engine.sheet.status(self.engine.mode, event, details)

    async def cmd_report(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self.reply(update, "⏳ Building reconciliation report…")
        await self.engine.daily_report(datetime.now(IST))

    # ------------------------------------------------------------ status
    async def cmd_help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self.reply(update, HELP)

    async def _capital_line(self, mode: str) -> str:
        try:
            cap, avail = await self.engine.capital_info(mode)
            return f"{fmt_money(cap)} (available {fmt_money(avail)})"
        except Exception as exc:
            return f"unavailable ({exc})"

    async def cmd_status(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        e = self.engine
        now = datetime.now(IST)
        mode = e.mode
        lines = [
            f"🤖 Mode: {mode.upper()}{'  ⏸ PAUSED' if e.store.get('paused') else ''}",
            f"Kite: {'✅ ' + e.kite.user.get('user_id', '') if e.kite.ready else '❌ not logged in (/login)'}",
            f"Lots – paper: {e.lots_setting('paper')} · live: {e.lots_setting('live')}",
            f"Paper capital: {await self._capital_line('paper')}",
        ]
        if e.kite.ready:
            lines.append(f"Live funds: {await self._capital_line('live')}")
        st = e.risk.day_stats(mode, now)
        lines.append(f"Today ({mode}): entries {st['entries']}/{e.cfg.max_trades_per_day} · realized "
                     f"{fmt_money(st['realized'])} · week {fmt_money(st['week_realized'])}")
        try:
            cap, _ = await e.capital_info(mode)
            ok, why = e.risk.can_open(mode, cap, now, e.unrealized(mode))
            lines.append("Risk gate: ✅ open" if ok else f"Risk gate: ⛔ {why}")
            if e.risk.emergency(mode, cap):
                lines.append("⚠️ Emergency capital protection active (allocation halved)")
        except Exception:
            pass
        if e.ctx is not None:
            lines.append(f"Regime: {e.ctx.regime} · SENSEX {e.last_spot or e.ctx.last['close']:.0f}")
        lines.append(f"Open positions: {len(e.positions)}")
        disabled = e.store.get("disabled", [])
        lines.append(f"Strategies enabled: {len(ALL_STRATEGIES) - len(disabled)}/{len(ALL_STRATEGIES)}")
        if e.last_error:
            lines.append(f"Last error: {e.last_error}")
        await self.reply(update, "\n".join(lines))

    async def cmd_positions(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.engine.positions:
            await self.reply(update, "No open positions.")
            return
        out = []
        for p in self.engine.positions:
            ltp = p.get("last_ltp", p["entry_price"])
            pnl = (ltp - p["entry_price"]) * p["qty"] + p.get("realized_gross", 0)
            out.append(
                f"{p['mode'].upper()} {p['symbol']} x{p['qty']} [{p['strategy']}]\n"
                f"  entry {p['entry_price']:.2f} · ltp {ltp:.2f} · P&L {fmt_money(pnl)}\n"
                f"  und.SL {p.get('sl_price') or p.get('stop_ref') or '-'} · target {p.get('target') or '-'} · "
                f"prem stop {p['prem_stop']:.2f} · trail {p.get('trail_level') or '-'}"
            )
        await self.reply(update, "\n".join(out))

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        mode = (ctx.args[0].lower() if ctx.args else self.engine.mode)
        if mode not in ("paper", "live"):
            await self.reply(update, "Usage: /trades [paper|live]")
            return
        day = datetime.now(IST).date().isoformat()
        rows = self.engine.store.trades(mode, since_day=day)
        if not rows:
            await self.reply(update, f"No {mode} trades today.")
            return
        lines = [f"{mode.upper()} trades today:"]
        for t in rows:
            lines.append(f"{t['entry_time'][11:16]}-{t['exit_time'][11:16]} {t['strategy']} {t['symbol']} x{t['qty']} "
                         f"{t['entry_price']:.2f}->{t['exit_price']:.2f} net {t['net_pnl']:+,.2f} ({t['exit_reason']})")
        lines.append(f"Total: {fmt_money(sum(t['net_pnl'] for t in rows))}")
        await self.reply(update, "\n".join(lines))

    async def cmd_pnl(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self.reply(update, self.engine.day_summary(datetime.now(IST)))

    async def cmd_regime(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        c = self.engine.ctx
        if c is None:
            await self.reply(update, "Regime not computed yet (market closed or warming up).")
            return
        await self.reply(update, f"Regime: {c.regime}\nAs of candle {c.df.index[-1]:%H:%M}\n{c.regime_detail}")

    async def cmd_funds(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.engine.kite.ready:
            await self.reply(update, "Kite not logged in. /login")
            return
        try:
            f = await self.engine.live_funds(max_age=0)
            await self.reply(update, f"💰 Zerodha equity funds\nNet: {fmt_money(f['net'])}\n"
                                     f"Available: {fmt_money(f['available'])}\nUtilised: {fmt_money(f['utilised'])}")
        except Exception as exc:
            await self.reply(update, f"Could not fetch funds: {exc}")

    # ------------------------------------------------------------ control
    async def cmd_mode(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        e = self.engine
        if not ctx.args:
            await self.reply(update, f"Current mode: {e.mode.upper()}. Usage: /mode paper | /mode live")
            return
        target = ctx.args[0].lower()
        if target == "paper":
            e.store.set("mode", "paper")
            self._live_confirm_until = None
            self._event("mode change", "paper")
            await self.reply(update, "📝 Switched to PAPER trading. Open live positions (if any) stay managed.")
        elif target == "live":
            if not e.kite.ready:
                await self.reply(update, "Kite not logged in — /login first.")
                return
            try:
                f = await e.live_funds(max_age=0)
            except Exception as exc:
                await self.reply(update, f"Cannot fetch live funds: {exc}")
                return
            self._live_confirm_until = datetime.now(IST) + timedelta(minutes=2)
            await self.reply(update, f"⚠️ LIVE trading places REAL orders with Zerodha.\n"
                                     f"Funds: net {fmt_money(f['net'])}, available {fmt_money(f['available'])}\n"
                                     f"Live lots: {e.lots_setting('live')}\n"
                                     f"Send /confirmlive within 2 minutes to switch.")
        else:
            await self.reply(update, "Usage: /mode paper | /mode live")

    async def cmd_confirm_live(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._live_confirm_until or datetime.now(IST) > self._live_confirm_until:
            await self.reply(update, "No pending live switch. Send /mode live first.")
            return
        self._live_confirm_until = None
        self.engine.store.set("mode", "live")
        self._event("mode change", "live")
        await self.reply(update, "🔴 LIVE trading enabled. New entries will place real orders. /mode paper to revert.")

    async def cmd_lots(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        e = self.engine
        if len(ctx.args) != 2 or ctx.args[0].lower() not in ("paper", "live"):
            await self.reply(update, f"Usage: /lots paper <n|auto> or /lots live <n|auto>\n"
                                     f"Now – paper: {e.lots_setting('paper')} · live: {e.lots_setting('live')}\n"
                                     f"auto = {e.cfg.alloc_pct:.0%} of available margin per trade, capped at {e.cfg.max_lots_cap} lots")
            return
        mode, val = ctx.args[0].lower(), ctx.args[1].lower()
        if val == "auto":
            e.store.set(f"lots_{mode}", "auto")
        else:
            try:
                n = int(val)
                assert 1 <= n <= MAX_FIXED_LOTS
            except Exception:
                await self.reply(update, f"Lots must be 'auto' or an integer 1–{MAX_FIXED_LOTS}.")
                return
            e.store.set(f"lots_{mode}", n)
        self._event("lots change", f"{mode}={e.lots_setting(mode)}")
        await self.reply(update, f"✅ {mode.upper()} lots set to {e.lots_setting(mode)} "
                                 f"(lot size {e.kite.lot_size()}). Bounded by {e.cfg.alloc_pct:.0%} of available margin; "
                                 f"{e.cfg.max_risk_per_trade_pct:.0%} per-trade loss cap applies.")

    async def cmd_capital(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        e = self.engine
        if not ctx.args:
            await self.reply(update, f"Paper balance: {fmt_money(e.risk.paper_balance())}. Usage: /capital <amount>")
            return
        try:
            amt = float(ctx.args[0].replace(",", "").replace("₹", ""))
            assert 1000 <= amt <= 1e9
        except Exception:
            await self.reply(update, "Amount must be a number between 1,000 and 1,000,000,000.")
            return
        if any(p["mode"] == "paper" for p in e.positions):
            await self.reply(update, "Close open paper positions first (/squareoff).")
            return
        e.risk.set_paper_capital(amt)
        self._event("paper capital", f"{amt:,.2f}")
        await self.reply(update, f"✅ Paper capital set to {fmt_money(amt)} (balance, peak and loss streak reset).")

    async def cmd_pause(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        self.engine.store.set("paused", True)
        self._event("pause", "new entries paused")
        await self.reply(update, "⏸ New entries paused. Open positions are still managed. /resume to continue.")

    async def cmd_resume(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        self.engine.store.set("paused", False)
        self._event("resume", "new entries resumed")
        await self.reply(update, "▶️ New entries resumed.")

    async def cmd_squareoff(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        n = await self.engine.squareoff_all("manual square-off (Telegram)")
        await self.reply(update, f"Square-off requested for {n} position(s).")

    async def cmd_strategies(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        disabled = set(self.engine.store.get("disabled", []))
        lines = [("⛔ " if s.sid in disabled else "✅ ") + s.describe() for s in ALL_STRATEGIES]
        await self.reply(update, "\n".join(lines))

    async def cmd_ids(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self.reply(update, ids_text(set(self.engine.store.get("disabled", []) or [])))

    async def _toggle(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE, enable: bool) -> None:
        if not ctx.args:
            await self.reply(update, "Usage: /enable <ID|all> or /disable <ID|all> (see /strategies)")
            return
        disabled = set(self.engine.store.get("disabled", []))
        arg = ctx.args[0].upper()
        if arg == "ALL":
            ids = [s.sid for s in ALL_STRATEGIES]
        else:
            match = [sid for sid in STRATEGY_MAP if sid == arg or sid.endswith("_" + arg) or arg in sid]
            if len(match) != 1:
                await self.reply(update, f"Unknown or ambiguous strategy '{ctx.args[0]}'. See /strategies")
                return
            ids = match
        disabled = disabled - set(ids) if enable else disabled | set(ids)
        self.engine.store.set("disabled", sorted(disabled))
        self._event("strategies", f"{'enabled' if enable else 'disabled'} {', '.join(ids)}")
        await self.reply(update, f"{'Enabled' if enable else 'Disabled'}: {', '.join(ids)}")

    async def cmd_enable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await self._toggle(update, ctx, True)

    async def cmd_disable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await self._toggle(update, ctx, False)

    # ------------------------------------------------------------ login
    async def cmd_login(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self.reply(update, self.engine.login_message())

    async def cmd_token(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not ctx.args:
            await self.reply(update, "Usage: /token <request_token or full redirect URL>")
            return
        raw = ctx.args[0]
        m = re.search(r"request_token=([A-Za-z0-9]+)", raw)
        token = m.group(1) if m else raw
        try:
            await asyncio.to_thread(self.engine.kite.exchange_request_token, token)
            await self.engine.on_login()
        except Exception as exc:
            await self.reply(update, f"Login failed: {exc}")
