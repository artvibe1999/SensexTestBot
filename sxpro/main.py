"""Entrypoint: python -m sxpro.main"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from .config import Config
from .engine import Engine
from .kite_service import KiteService
from .store import Store
from .sheets import SheetLogHandler
from .telegram_bot import TelegramController
from .web import start_web


async def amain() -> None:
    cfg = Config()
    missing = [k for k in ("KITE_API_KEY", "KITE_API_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"missing env vars: {', '.join(missing)}")
    store = Store(cfg.db_path)
    kite = KiteService(cfg)
    engine = Engine(cfg, store, kite)
    tg = TelegramController(cfg, engine)
    logging.getLogger().addHandler(SheetLogHandler(engine.sheet, lambda: engine.mode))
    sheet_task = asyncio.create_task(engine.sheet.run())
    await tg.start()
    runner = await start_web(engine, cfg.web_port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    task = asyncio.create_task(engine.run())
    await stop.wait()
    task.cancel()
    await engine.say("🛑 Bot stopping (container shutdown). Open positions are saved and resume on restart.")
    await engine.drain_outbox()
    engine.sheet.status(engine.mode, "shutdown", engine.status_text())
    sheet_task.cancel()
    await asyncio.to_thread(engine.sheet.flush)
    await tg.stop()
    await runner.cleanup()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(amain())


if __name__ == "__main__":
    main()
