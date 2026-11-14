"""Log-tab level of Telegram notifications."""
import asyncio
from types import SimpleNamespace

from sxpro.engine import Engine


def _engine():
    eng = Engine.__new__(Engine)
    eng.rows = []
    eng.sheet = SimpleNamespace(log=lambda mode, level, src, text: eng.rows.append(level))
    eng.store = SimpleNamespace(get=lambda k, d=None: "paper" if k == "mode" else d)
    eng._sender = None
    eng.sent = []

    async def notify(text):
        eng.sent.append(text)
    eng.notify = notify
    return eng


def test_emoji_sets_level_by_default():
    eng = _engine()
    asyncio.run(eng.say("🛑 PAPER daily loss limit reached"))
    asyncio.run(eng.say("⚠️ something odd"))
    asyncio.run(eng.say("✅ started"))
    assert eng.rows == ["ERROR", "WARN", "INFO"]


def test_shutdown_notice_logs_as_info_but_keeps_its_text():
    eng = _engine()
    msg = "🛑 Bot stopping (container shutdown). Open positions are saved and resume on restart."
    asyncio.run(eng.say(msg, level="INFO"))
    assert eng.rows == ["INFO"] and eng.sent == [msg]
