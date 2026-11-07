from sxpro.strategies import ALL_STRATEGIES, STRATEGY_MAP
from sxpro.telegram_bot import HELP, MENU, ids_text


def test_ids_lists_every_strategy_with_state():
    text = ids_text({"SENSEX_IB_09", "SENSEX_TREND_04"})
    assert "18/20 enabled" in text
    for s in ALL_STRATEGIES:
        assert s.sid in text
    assert "⛔ SENSEX_IB_09" in text and "✅ SENSEX_VWAP_03" in text


def test_short_ids_resolve_uniquely():
    # same matching rule as /enable and /disable
    for s in ALL_STRATEGIES:
        short = s.sid.replace("SENSEX_", "")
        match = [sid for sid in STRATEGY_MAP if sid == short or sid.endswith("_" + short) or short in sid]
        assert match == [s.sid], (short, match)


def test_menu_and_help_cover_ids():
    assert "ids" in dict(MENU) and "/ids" in HELP
