"""Kite price checks: one retry on a network blip, Telegram only after repeated failures."""
import asyncio
from datetime import date

import pytest
import requests

from sxpro import kite_service
from sxpro.config import Config
from sxpro.engine import NET_FAIL_ALERT_AFTER
from sxpro.kite_service import INDEX_SYMBOL, KiteService, TokenError

from .fakes import FakeKite, synthetic_candles
from .test_review import cfg, live_engine  # noqa: F401  (fixture)

TIMEOUT = requests.exceptions.ReadTimeout("api.kite.trade Read timed out. (read timeout=15)")


def service(monkeypatch, outcomes):
    """KiteService whose kite.quote returns/raises the given outcomes in order."""
    monkeypatch.setattr(kite_service, "QUOTE_RETRY_DELAY_S", 0)
    ks = KiteService(Config())
    ks._quote.gap = 0
    calls = []

    def fake_quote(keys):
        calls.append(keys)
        o = outcomes.pop(0)
        if isinstance(o, BaseException):
            raise o
        return o
    monkeypatch.setattr(ks.kite, "quote", fake_quote)
    return ks, calls


def test_quote_retries_once_after_timeout(cfg, monkeypatch):
    ks, calls = service(monkeypatch, [TIMEOUT, {INDEX_SYMBOL: {"last_price": 82000.0}}])
    assert ks.quote([INDEX_SYMBOL])[INDEX_SYMBOL]["last_price"] == 82000.0
    assert len(calls) == 2


def test_quote_gives_up_after_second_timeout(cfg, monkeypatch):
    ks, calls = service(monkeypatch, [TIMEOUT, requests.exceptions.ConnectionError("reset")])
    with pytest.raises(requests.exceptions.ConnectionError):
        ks.quote([INDEX_SYMBOL])
    assert len(calls) == 2


def test_quote_does_not_retry_other_errors(cfg, monkeypatch):
    from kiteconnect import exceptions as kex
    ks, calls = service(monkeypatch, [kex.TokenException("expired")])
    with pytest.raises(TokenError):
        ks.quote([INDEX_SYMBOL])
    ks, calls = service(monkeypatch, [kex.InputException("bad symbol")])
    with pytest.raises(kex.InputException):
        ks.quote([INDEX_SYMBOL])
    assert len(calls) == 1


def test_network_errors_alert_only_after_streak_and_report_recovery(cfg):
    eng, _, msgs = live_engine(cfg, FakeKite(synthetic_candles(3), date(2026, 11, 5)))

    async def run():
        for _ in range(NET_FAIL_ALERT_AFTER - 1):
            await eng.on_tick_error(TIMEOUT)
        assert msgs == []                          # a blip or two: log only
        await eng.on_tick_ok()
        for _ in range(NET_FAIL_ALERT_AFTER - 1):  # streak was reset by the good tick
            await eng.on_tick_error(TIMEOUT)
        assert msgs == []
        await eng.on_tick_error(TIMEOUT)
        assert len(msgs) == 1 and msgs[0].startswith("⚠️ Kite not responding")
        await eng.on_tick_error(TIMEOUT)           # no repeat alert while still down
        assert len(msgs) == 1
        await eng.on_tick_ok()
        assert msgs[-1] == "✅ Kite connection recovered."
    asyncio.run(run())
    assert "Read timed out" in eng.last_error


def test_other_errors_still_alert_immediately(cfg):
    eng, _, msgs = live_engine(cfg, FakeKite(synthetic_candles(3), date(2026, 11, 5)))
    asyncio.run(eng.on_tick_error(ValueError("boom")))
    assert msgs == ["⚠️ Engine error: boom"]
