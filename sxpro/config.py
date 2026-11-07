"""Static configuration loaded from environment variables (.env).

Runtime-tunable values (mode, lots, paper capital, enabled strategies) live in
the SQLite state store and are changed from Telegram; the env values below are
only their first-boot defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(float(_env(name, str(default))))
    except ValueError:
        return default


def _hhmm(value: str, default: str) -> time:
    try:
        h, m = (value or default).split(":")
        return time(int(h), int(m))
    except Exception:
        h, m = default.split(":")
        return time(int(h), int(m))


@dataclass(frozen=True)
class Config:
    # Kite
    kite_api_key: str = field(default_factory=lambda: _env("KITE_API_KEY"))
    kite_api_secret: str = field(default_factory=lambda: _env("KITE_API_SECRET"))
    kite_access_token: str = field(default_factory=lambda: _env("KITE_ACCESS_TOKEN"))
    kite_user_id: str = field(default_factory=lambda: _env("KITE_USER_ID"))

    # Telegram
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))

    # Web / login
    bot_domain: str = field(default_factory=lambda: _env("BOT_DOMAIN"))
    login_prompt_time: time = field(default_factory=lambda: _hhmm(_env("LOGIN_PROMPT_TIME"), "08:30"))
    web_port: int = field(default_factory=lambda: _int("WEB_PORT", 8080))

    # Trading defaults (first boot only; then controlled from Telegram)
    product: str = field(default_factory=lambda: _env("PRODUCT", "MIS") or "MIS")
    default_paper_capital: float = field(default_factory=lambda: _float("PAPER_CAPITAL", 50000))
    # cap for auto sizing; default = SENSEX freeze qty 1000 / lot 20
    max_lots_cap: int = field(default_factory=lambda: _int("AUTO_MAX_LOTS", 50))

    # Capital-management framework (fractions of capital)
    # share of available margin deployed per trade (paper balance / Zerodha available margin)
    alloc_pct: float = field(default_factory=lambda: _float("MARGIN_UTILIZATION_PCT", 0.90))
    max_risk_per_trade_pct: float = field(default_factory=lambda: _float("TRADE_LOSS_CAP_PCT", 0.10))
    max_daily_loss_pct: float = field(default_factory=lambda: _float("DAILY_LOSS_LIMIT_PCT", 0.10))
    max_weekly_loss_pct: float = field(default_factory=lambda: _float("WEEKLY_LOSS_LIMIT_PCT", 0.25))
    max_trades_per_day: int = field(default_factory=lambda: _int("MAX_TRADES_PER_DAY", 3))
    max_consecutive_losses: int = field(default_factory=lambda: _int("MAX_CONSECUTIVE_LOSSES", 4))
    cooloff_hours: float = field(default_factory=lambda: _float("COOLOFF_HOURS", 24))
    emergency_drawdown_pct: float = field(default_factory=lambda: _float("EMERGENCY_DRAWDOWN_PCT", 0.20))
    max_open_positions: int = field(default_factory=lambda: _int("MAX_OPEN_POSITIONS", 1))

    # Strike selection
    max_spread_pct: float = field(default_factory=lambda: _float("MAX_SPREAD_PCT", 0.01))
    # Beyond-spec strike limits (strategy delta targets are unchanged)
    premium_cap: float = field(default_factory=lambda: _float("PREMIUM_CAP", 900))
    zero_dte_premium_cap: float = field(default_factory=lambda: _float("ZERO_DTE_PREMIUM_CAP", 250))
    delta_widen_up: float = field(default_factory=lambda: _float("DELTA_WIDEN_UP", 0.15))
    delta_widen_down: float = field(default_factory=lambda: _float("DELTA_WIDEN_DOWN", 0.05))
    delta_max_cap: float = field(default_factory=lambda: _float("DELTA_MAX_CAP", 0.80))
    delta_min_floor: float = field(default_factory=lambda: _float("DELTA_MIN_FLOOR", 0.25))
    risk_free_rate: float = field(default_factory=lambda: _float("RISK_FREE_RATE", 0.065))

    # Engine timing
    poll_seconds: float = field(default_factory=lambda: _float("POLL_SECONDS", 2.0))
    candle_delay_seconds: float = field(default_factory=lambda: _float("CANDLE_DELAY_SECONDS", 4.0))
    entry_start: time = field(default_factory=lambda: _hhmm(_env("ENTRY_START"), "09:20"))
    entry_cutoff: time = field(default_factory=lambda: _hhmm(_env("ENTRY_CUTOFF"), "15:10"))
    squareoff_time: time = field(default_factory=lambda: _hhmm(_env("SQUAREOFF_TIME"), "15:20"))
    summary_time: time = field(default_factory=lambda: _hhmm(_env("SUMMARY_TIME"), "15:35"))

    # Live order execution
    order_fill_timeout_s: float = field(default_factory=lambda: _float("ORDER_FILL_TIMEOUT_S", 8))
    limit_buffer_pct: float = field(default_factory=lambda: _float("LIMIT_BUFFER_PCT", 0.01))

    # Google Sheet: service-account key (Sheets API), or the sheet's Apps Script web app
    google_sheet_id: str = field(default_factory=lambda: _env("GOOGLE_SHEET_ID"))
    google_sa_json: str = field(default_factory=lambda: _env("GOOGLE_SERVICE_ACCOUNT_JSON"))
    sheets_webhook_url: str = field(default_factory=lambda: _env("SHEETS_WEBHOOK_URL"))
    sheets_secret: str = field(default_factory=lambda: _env("SHEETS_SECRET"))
    report_time: time = field(default_factory=lambda: _hhmm(_env("REPORT_TIME"), "16:00"))
    status_interval_min: int = field(default_factory=lambda: _int("STATUS_INTERVAL_MIN", 15))

    data_dir: str = field(default_factory=lambda: _env("DATA_DIR", "data") or "data")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "sxpro.db")

    @property
    def token_path(self) -> str:
        return os.path.join(self.data_dir, "token.json")

    @property
    def redirect_url(self) -> str:
        return f"https://{self.bot_domain}/kite/callback" if self.bot_domain else ""


MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
