"""SQLite persistence: runtime settings, open positions, closed trades, risk state."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any

from .config import IST

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    id    TEXT PRIMARY KEY,
    mode  TEXT NOT NULL,
    data  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id   TEXT NOT NULL,
    mode          TEXT NOT NULL,
    strategy      TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    option_type   TEXT NOT NULL,
    qty           INTEGER NOT NULL,
    entry_price   REAL NOT NULL,
    exit_price    REAL NOT NULL,
    gross_pnl     REAL NOT NULL,
    charges       REAL NOT NULL,
    net_pnl       REAL NOT NULL,
    entry_time    TEXT NOT NULL,
    exit_time     TEXT NOT NULL,
    exit_reason   TEXT NOT NULL,
    trade_day     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_trades_mode_day ON trades(mode, trade_day);
CREATE TABLE IF NOT EXISTS events (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    TEXT NOT NULL,
    kind  TEXT NOT NULL,
    text  TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(trades)").fetchall()}
        if "legs" not in cols:  # migration: per-order exit legs + charge source
            self._db.execute("ALTER TABLE trades ADD COLUMN legs TEXT")
            self._db.execute("ALTER TABLE trades ADD COLUMN cost_source TEXT DEFAULT 'estimate'")

    # ---------------- settings ----------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM settings WHERE key=?", (key,))

    def setdefault(self, key: str, value: Any) -> Any:
        current = self.get(key)
        if current is None:
            self.set(key, value)
            return value
        return current

    # ---------------- positions ----------------
    def save_position(self, pos_id: str, mode: str, data: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO positions(id, mode, data) VALUES(?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data, mode=excluded.mode",
                (pos_id, mode, json.dumps(data, default=str)),
            )

    def delete_position(self, pos_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM positions WHERE id=?", (pos_id,))

    def load_positions(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM positions").fetchall()
        return [json.loads(r["data"]) for r in rows]

    # ---------------- trades ----------------
    def record_trade(self, t: dict) -> None:
        cols = [
            "position_id", "mode", "strategy", "symbol", "option_type", "qty",
            "entry_price", "exit_price", "gross_pnl", "charges", "net_pnl",
            "entry_time", "exit_time", "exit_reason", "trade_day", "legs", "cost_source",
        ]
        t = {**t, "legs": json.dumps(t.get("legs") or []), "cost_source": t.get("cost_source", "estimate")}
        with self._lock:
            self._db.execute(
                f"INSERT INTO trades({','.join(cols)}) VALUES({','.join('?' * len(cols))})",  # nosec B608 - fixed column list, values bound
                [t[c] for c in cols],
            )

    def update_trade_costs(self, trade_id: int, charges: float, source: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE trades SET charges=?, net_pnl=ROUND(gross_pnl-?, 2), cost_source=? WHERE id=?",
                (round(charges, 2), round(charges, 2), source, trade_id),
            )

    def trades(self, mode: str, since_day: str | None = None, until_day: str | None = None) -> list[dict]:
        sql = "SELECT * FROM trades WHERE mode=?"
        args: list[Any] = [mode]
        if since_day:
            sql += " AND trade_day>=?"
            args.append(since_day)
        if until_day:
            sql += " AND trade_day<=?"
            args.append(until_day)
        sql += " ORDER BY id"
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def recent_trades(self, mode: str, limit: int) -> list[dict]:
        """Newest first."""
        with self._lock:
            return [dict(r) for r in self._db.execute(
                "SELECT id, net_pnl FROM trades WHERE mode=? ORDER BY id DESC LIMIT ?", (mode, limit)).fetchall()]

    def last_trade_id(self, mode: str) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(id), 0) AS m FROM trades WHERE mode=?", (mode,)).fetchone()
        return int(row["m"])

    def realized_pnl(self, mode: str, since_day: str | None = None) -> float:
        sql = "SELECT COALESCE(SUM(net_pnl), 0) AS s FROM trades WHERE mode=?"
        args: list[Any] = [mode]
        if since_day:
            sql += " AND trade_day>=?"
            args.append(since_day)
        with self._lock:
            return float(self._db.execute(sql, args).fetchone()["s"])

    # ---------------- events ----------------
    def log_event(self, kind: str, text: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events(ts, kind, text) VALUES(?, ?, ?)",
                (datetime.now(IST).isoformat(timespec="seconds"), kind, text),
            )
