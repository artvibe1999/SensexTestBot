from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sxpro.config import IST
from sxpro.liquidity import _depth_obi, analyze_liquidity, strategy_confluence
from sxpro.market import build_context


def make_context():
    start = datetime(2026, 11, 16, 9, 15, tzinfo=IST)
    index = pd.date_range(start, periods=36, freq="5min")
    close = 80000 + np.arange(len(index), dtype=float) * 8
    frame = pd.DataFrame({
        "open": close - 4,
        "high": close + 12,
        "low": close - 12,
        "close": close,
        "volume": np.linspace(1000, 2500, len(index)),
    }, index=index)
    now = index[-1] + timedelta(minutes=5)
    return build_context(frame, now, {"open": 79800, "high": 80100, "low": 79600, "close": 79900})


def test_depth_imbalance_is_bounded_and_directional():
    quote = {"depth": {
        "buy": [{"quantity": 900}, {"quantity": 500}],
        "sell": [{"quantity": 100}, {"quantity": 100}],
    }}
    value = _depth_obi(quote)
    assert value is not None
    assert 0 < value <= 1
    assert _depth_obi({}) is None


def test_liquidity_analysis_uses_causal_context_and_returns_schema():
    ctx = make_context()
    result = analyze_liquidity(ctx, None)
    assert result["available"] is True
    assert 0 <= result["score"] <= 100
    assert isinstance(result["zones"], list)
    assert result["event"] in {
        "none", "bullish_sweep_reclaim", "bearish_sweep_reclaim",
        "bullish_breakout", "bearish_breakout",
    }


def test_strategy_confluence_is_ranking_only_and_category_aware():
    liquidity = {
        "available": True, "event": "bullish_sweep_reclaim", "direction": 1,
        "obi": 0.35,
    }
    reversal, _ = strategy_confluence(liquidity, "CE", "reversal")
    breakout, _ = strategy_confluence(liquidity, "CE", "breakout")
    opposite, _ = strategy_confluence(liquidity, "PE", "reversal")
    assert reversal == 2
    assert breakout >= 0
    assert opposite == 0
