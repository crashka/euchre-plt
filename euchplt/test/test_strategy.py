# -*- coding: utf-8 -*-

from os import environ
environ['EUCHPLT_CONFIG_FILE'] = 'test_config.yml'

from euchplt.strategy import get_strategy
from euchplt.strategy import StrategyRandom, StrategySimple, StrategySmart

def test_get_strategy():
    """Primarily test instantiation by name, and proper parameter overrides
    across seeded strategies.  More detailed strategy-specific functionality
    is tested in individual per-strategy test files.
    """
    strat = get_strategy('Alfa 1')
    assert isinstance(strat, StrategyRandom)
    assert strat.seed is None

    strat = get_strategy('Alfa 2')
    assert isinstance(strat, StrategyRandom)
    assert strat.seed == 99999

    strat = get_strategy('Bravo 1')
    assert isinstance(strat, StrategySimple)
    assert not strat.aggressive

    strat = get_strategy('Bravo 2')
    assert isinstance(strat, StrategySimple)
    assert strat.aggressive

    strat = get_strategy('Charlie 1')
    assert isinstance(strat, StrategySmart)
    assert not strat.hand_analysis
    assert isinstance(strat.bid_thresh, list)
    assert isinstance(strat.alone_margin, list)
    assert isinstance(strat.def_alone_thresh, list)
    assert len(strat.bid_thresh) == 8
    assert len(strat.alone_margin) == 8
    assert len(strat.def_alone_thresh) == 8

    strat = get_strategy('Charlie 2')
    assert isinstance(strat, StrategySmart)
    assert isinstance(strat.hand_analysis, dict)
    assert isinstance(strat.bid_thresh, list)
    assert isinstance(strat.alone_margin, list)
    assert isinstance(strat.def_alone_thresh, list)
    assert len(strat.hand_analysis) == 6
    assert len(strat.bid_thresh) == 8
    assert len(strat.alone_margin) == 8
    assert len(strat.def_alone_thresh) == 8
