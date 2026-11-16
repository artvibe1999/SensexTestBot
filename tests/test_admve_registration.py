from sxpro.strategies import ALL_STRATEGIES, STRATEGY_MAP
from sxpro.strategies.admve import AdaptiveDirectionalMomentum
from sxpro.strategies.tuning import VERIFIED_INDEX


def test_admve_is_registered_without_false_verified_label():
    assert "SENSEX_ADMVE_80" in STRATEGY_MAP
    assert any(isinstance(s, AdaptiveDirectionalMomentum) for s in ALL_STRATEGIES)
    assert "SENSEX_ADMVE_80" not in VERIFIED_INDEX


def test_admve_configuration_is_single_leg_intraday_candidate():
    strategy = STRATEGY_MAP["SENSEX_ADMVE_80"]
    assert strategy.delta_min < strategy.delta_target < strategy.delta_max
    assert strategy.end.hour == 14 and strategy.end.minute == 30
    assert strategy.time_exit.hour == 15 and strategy.time_exit.minute == 15
    assert strategy.needs == ("liquidity", "futures_depth")
