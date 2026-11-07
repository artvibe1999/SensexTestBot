"""Tiny HTTP server for the Kite Connect login redirect (served behind Caddy/HTTPS)."""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time

from aiohttp import web

from .engine import Engine

log = logging.getLogger(__name__)

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>SENSEX PRO</title><style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem}}</style>
</head><body><h2>{title}</h2><p>{body}</p></body></html>"""

TOKEN_RE = re.compile(r"^[A-Za-z0-9]{16,64}$")
MAX_ATTEMPTS, WINDOW_S = 5, 600
LOOPBACK = ("127.0.0.1", "::1")


def _page(title: str, body: str, status: int = 200) -> web.Response:
    return web.Response(text=PAGE.format(title=html.escape(title), body=html.escape(body)),
                        content_type="text/html", status=status,
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def build_app(engine: Engine) -> web.Application:
    attempts: list[float] = []

    async def callback(request: web.Request) -> web.Response:
        token = request.query.get("request_token", "")
        if request.query.get("status") != "success" or not TOKEN_RE.match(token):
            return _page("Login not completed", "No valid request token received.", 400)
        now = time.monotonic()
        attempts[:] = [t for t in attempts if now - t < WINDOW_S]
        if len(attempts) >= MAX_ATTEMPTS:
            return _page("Too many attempts", "Try again in a few minutes.", 429)
        attempts.append(now)
        try:
            user = await asyncio.to_thread(engine.kite.exchange_request_token, token)
            await engine.on_login()
            return _page("✅ Logged in", f"Kite session active for {user.get('user_id', '')}. You can close this tab.")
        except Exception as exc:
            log.warning("token exchange failed: %s", exc)
            await engine.say(f"❌ Kite login failed: {exc}")
            return _page("Login failed", "Token exchange failed; see Telegram.", 500)

    async def health(request: web.Request) -> web.Response:
        if request.remote not in LOOPBACK:  # public: liveness only, no internals
            return web.json_response({"ok": True})
        return web.json_response({"ok": True, "kite_ready": engine.kite.ready, "mode": engine.mode,
                                  "positions": len(engine.positions), "sheet": engine.sheet.stats()})

    app = web.Application(client_max_size=64 * 1024)
    app.router.add_get("/kite/callback", callback)
    app.router.add_get("/health", health)
    return app


async def start_web(engine: Engine, port: int) -> web.AppRunner:
    runner = web.AppRunner(build_app(engine), access_log=None)
    await runner.setup()
    # 0.0.0.0 is required so Caddy (another container) can reach it; the port is not published.
    await web.TCPSite(runner, "0.0.0.0", port).start()  # nosec B104
    return runner
