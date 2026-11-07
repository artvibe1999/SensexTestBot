"""16:00 IST reconciliation: fetch the day's live (Kite) and paper trades, compute the
correct P&L after Zerodha's charges and taxes, update the GCS HTML report, and log the
final trades to the Google Sheet."""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import requests

from .charges import OrderLeg, formula_charges, order_charges
from .config import IST, Config
from .kite_service import KiteService
from .risk import RiskManager
from .sheets import SheetLogger
from .store import Store

log = logging.getLogger(__name__)

META_TOKEN = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
DATA_RE = re.compile(r"const D=(\{.*?\});\nconst inr", re.S)
TEMPLATE = os.path.join(os.path.dirname(__file__), "report_template.html")


# ------------------------------------------------------------------ GCS
class GCS:
    def __init__(self, bucket: str):
        self.bucket = bucket

    @staticmethod
    def _token() -> str:
        r = requests.get(META_TOKEN, headers={"Metadata-Flavor": "Google"}, timeout=5)
        r.raise_for_status()
        return r.json()["access_token"]

    def get(self, name: str) -> str | None:
        url = (f"https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/"
               f"{urllib.parse.quote(name, safe='')}?alt=media")
        r = requests.get(url, headers={"Authorization": f"Bearer {self._token()}"}, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content.decode("utf-8")

    def put(self, name: str, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        boundary = uuid.uuid4().hex
        meta = json.dumps({"name": name, "contentType": content_type, "cacheControl": "no-cache, max-age=0"})
        payload = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                   f"--{boundary}\r\nContent-Type: {content_type}\r\n\r\n").encode() + body.encode("utf-8") + \
                  f"\r\n--{boundary}--".encode()
        r = requests.post(f"https://storage.googleapis.com/upload/storage/v1/b/{self.bucket}/o?uploadType=multipart",
                          headers={"Authorization": f"Bearer {self._token()}",
                                   "Content-Type": f"multipart/related; boundary={boundary}"},
                          data=payload, timeout=60)
        r.raise_for_status()


def _hhmm(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%H:%M")
    s = str(v or "")
    m = re.search(r"(\d\d:\d\d)", s[10:] if len(s) > 10 else s)
    return m.group(1) if m else ""


def _is_sensex_option(sym: str) -> bool:
    return sym.startswith("SENSEX") and sym[-2:] in ("CE", "PE")


class DailyReporter:
    def __init__(self, cfg: Config, kite: KiteService, store: Store, risk: RiskManager, sheet: SheetLogger):
        self.cfg, self.kite, self.store, self.risk, self.sheet = cfg, kite, store, risk, sheet

    @property
    def object_name(self) -> str:
        return f"r/{self.cfg.report_token}/index.html"

    @property
    def public_url(self) -> str:
        return f"https://storage.googleapis.com/{self.cfg.report_bucket}/{self.object_name}"

    # ------------------------------------------------------------ live
    def live_rows(self, day: date) -> list[dict]:
        orders = [o for o in self.kite.orders()
                  if o.get("status") == "COMPLETE" and o.get("exchange") == "BFO"
                  and _is_sensex_option(o.get("tradingsymbol", "")) and int(o.get("filled_quantity") or 0) > 0]
        if not orders:
            return []
        legs = [OrderLeg(o["order_id"], o["tradingsymbol"], o["transaction_type"], int(o["filled_quantity"]),
                         float(o["average_price"]), o["exchange"], o["product"], o["order_type"], o["variety"])
                for o in orders]
        costs, cost_src = order_charges(self.kite.kite, legs)
        try:
            day_pos = {p["tradingsymbol"]: p for p in self.kite.positions().get("day", [])}
        except Exception as exc:
            log.warning("positions unavailable: %s", exc)
            day_pos = {}
        by_sym: dict[str, list[dict]] = defaultdict(list)
        for o in orders:
            by_sym[o["tradingsymbol"]].append(o)
        rows = []
        for sym, os_ in sorted(by_sym.items()):
            buys = [o for o in os_ if o["transaction_type"] == "BUY"]
            sells = [o for o in os_ if o["transaction_type"] == "SELL"]
            bq = sum(int(o["filled_quantity"]) for o in buys)
            sq = sum(int(o["filled_quantity"]) for o in sells)
            bavg = sum(int(o["filled_quantity"]) * float(o["average_price"]) for o in buys) / bq if bq else 0.0
            savg = sum(int(o["filled_quantity"]) * float(o["average_price"]) for o in sells) / sq if sq else 0.0
            times = sorted(o.get("exchange_timestamp") or o.get("order_timestamp") for o in os_)
            tags = {o.get("tag") == "sxpro" for o in os_}
            who = "Bot" if tags == {True} else "Manual" if tags == {False} else "Bot+Manual"
            p = day_pos.get(sym)
            if p is not None:
                gross, pnl_src = float(p.get("pnl", 0.0)), "zerodha"
            else:
                gross, pnl_src = sq * savg - bq * bavg, "computed"
            cost = round(sum(costs[o["order_id"]] for o in os_), 2)
            rows.append({
                "date": day.isoformat(), "symbol": sym, "who": who,
                "entry": _hhmm(times[0]), "exit": _hhmm(times[-1]) if sells else "",
                "bought": bq, "buy_avg": round(bavg, 2), "sold": sq, "sell_avg": round(savg, 2),
                "open_qty": bq - sq, "gross": round(gross, 2), "cost": cost, "net": round(gross - cost, 2),
                "pnl_source": pnl_src, "cost_source": cost_src,
            })
        self._correct_bot_live(day, rows)
        return rows

    def _correct_bot_live(self, day: date, rows: list[dict]) -> None:
        """Replace estimated charges on the bot's live trades with Zerodha's numbers."""
        by_sym = {r["symbol"]: r for r in rows if r["who"] == "Bot"}
        trades = self.store.trades("live", since_day=day.isoformat(), until_day=day.isoformat())
        for t in trades:
            r = by_sym.get(t["symbol"])
            if not r or not r["bought"]:
                continue
            share = t["qty"] / r["bought"]
            self.store.update_trade_costs(t["id"], r["cost"] * share, r["cost_source"])

    # ------------------------------------------------------------ paper
    def paper_rows(self, day: date) -> list[dict]:
        trades = self.store.trades("paper", since_day=day.isoformat(), until_day=day.isoformat())
        if not trades:
            return []
        legs_by_trade: dict[int, list[OrderLeg]] = {}
        for t in trades:
            exits = json.loads(t.get("legs") or "[]") or [[t["exit_price"], t["qty"]]]
            legs = [OrderLeg(f"PAPER{t['id']}B", t["symbol"], "BUY", t["qty"], t["entry_price"])]
            legs += [OrderLeg(f"PAPER{t['id']}S{i}", t["symbol"], "SELL", int(q), float(px))
                     for i, (px, q) in enumerate(exits)]
            legs_by_trade[t["id"]] = legs
        all_legs = [l for ls in legs_by_trade.values() for l in ls]
        if self.kite.ready:
            costs, src = order_charges(self.kite.kite, all_legs)
        else:
            costs, src = {l.order_id: formula_charges(l) for l in all_legs}, "estimate"
        rows, delta = [], 0.0
        lot = max(1, self.kite.lot_size())
        for t in trades:
            cost = round(sum(costs[l.order_id] for l in legs_by_trade[t["id"]]), 2)
            delta += t["charges"] - cost
            self.store.update_trade_costs(t["id"], cost, src)
            rows.append({
                "id": t["id"], "date": day.isoformat(), "setup": t["strategy"], "lots": t["qty"] // lot,
                "symbol": t["symbol"],
                "qty": t["qty"], "entry": t["entry_time"][11:16], "exit": t["exit_time"][11:16],
                "reason": t["exit_reason"], "gross": round(t["gross_pnl"], 2), "cost": cost,
                "net": round(t["gross_pnl"] - cost, 2), "cost_source": src,
            })
        if abs(delta) >= 0.01:
            self.store.set("paper_balance", round(self.risk.paper_balance() + delta, 2))
        return rows

    # ------------------------------------------------------------ report + sheet
    def _merge(self, html: str | None, day: date, live: list[dict] | None, paper: list[dict]) -> str:
        if html and DATA_RE.search(html):
            data = json.loads(DATA_RE.search(html).group(1))
            page = html
        else:
            page = open(TEMPLATE, encoding="utf-8").read()
            data = {"since": day.isoformat(), "paper": {"trades": [], "days": []},
                    "live": {"trades": [], "days": []}, "backtest_url": ""}
        d = day.isoformat()
        for kind, rows in (("paper", paper), ("live", live)):
            if rows is None:  # live unavailable (Kite logged out): keep what was there
                continue
            sec = data.setdefault(kind, {"trades": [], "days": []})
            sec["trades"] = [r for r in sec.get("trades", []) if r.get("date") != d] + rows
            sec["days"] = sorted(set(sec.get("days", [])) | {d})
        data["generated_at"] = datetime.now(IST).isoformat(timespec="seconds")
        blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        if "__DATA__" in page:
            return page.replace("__DATA__", blob)
        m = DATA_RE.search(page)
        return page[: m.start(1)] + blob + page[m.end(1):]

    def _sheet_trades(self, live: list[dict] | None, paper: list[dict]) -> None:
        """Append final trades to the sheet's Trades tab, each one only once per day."""
        day = (paper or live or [{}])[0].get("date")
        if not day:
            return
        key_name = f"sheet_trades_{day}"
        logged = set(self.store.get(key_name, []) or [])
        for mode, rows in (("paper", paper), ("live", live or [])):
            running = 0.0
            for r in sorted(rows, key=lambda x: x.get("exit") or "99"):
                running += r["net"]
                key = f"paper|{r.get('id')}" if mode == "paper" else f"live|{r['symbol']}"
                if key in logged or (mode == "live" and r["open_qty"]):
                    continue  # already logged, or still open (logged once it is closed)
                logged.add(key)
                exit_t = f"{r['date']} {r['exit']}:00" if r.get("exit") else f"{r['date']} (open)"
                if mode == "paper":
                    self.sheet.trade([exit_t, mode, r["setup"], r["reason"], r["lots"], r["gross"], r["cost"],
                                      r["net"], round(running, 2), r["symbol"], r["qty"], f"{r['date']} {r['entry']}:00",
                                      "", "", r["cost_source"]])
                else:
                    lots = r["bought"] // max(1, self.kite.lot_size())
                    self.sheet.trade([exit_t, mode, r["who"], "day position" + (f" (open {r['open_qty']})" if r["open_qty"] else ""),
                                      lots, r["gross"], r["cost"], r["net"], round(running, 2), r["symbol"], r["bought"],
                                      f"{r['date']} {r['entry']}:00", r["buy_avg"], r["sell_avg"], r["cost_source"]])
        self.store.set(key_name, sorted(logged))

    def run(self, day: date) -> str:
        live = self.live_rows(day) if self.kite.ready else None
        paper = self.paper_rows(day)
        url = ""
        if self.cfg.report_bucket and self.cfg.report_token:
            gcs = GCS(self.cfg.report_bucket)
            html = gcs.get(self.object_name)
            gcs.put(self.object_name, self._merge(html, day, live, paper))
            url = self.public_url
        self._sheet_trades(live, paper)
        lines = [f"🧾 Reconciled report {day:%d %b %Y} (after Zerodha charges & taxes)"]
        p_net = sum(r["net"] for r in paper)
        lines.append(f"PAPER: {len(paper)} trades · gross {sum(r['gross'] for r in paper):+,.2f} · "
                     f"charges {sum(r['cost'] for r in paper):,.2f} · net {p_net:+,.2f}")
        if live is None:
            lines.append("LIVE: not fetched (Kite not logged in)")
        else:
            bot = [r for r in live if r["who"] != "Manual"]
            lines.append(f"LIVE: {len(live)} contracts ({len(bot)} bot) · gross {sum(r['gross'] for r in live):+,.2f} · "
                         f"charges {sum(r['cost'] for r in live):,.2f} · net {sum(r['net'] for r in live):+,.2f}")
            if any(r["open_qty"] for r in live):
                lines.append("⚠️ Some live quantity is still open (marked at last price).")
        lines.append(f"Paper balance: ₹{self.risk.paper_balance():,.2f}")
        if url:
            lines.append(f"Report: {url}")
        return "\n".join(lines)
