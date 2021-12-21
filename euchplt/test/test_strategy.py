# -*- coding: utf-8 -*-

from euchplt.core import cfg
from euchplt.strategy import Strategy
from euchplt.strategy import StrategyRandom, StrategySimple, StrategySmart

cfg.load('test_config.yml')

def test_strategy_new():
    """Primarily test instantiation by name, and proper parameter overrides
    across seeded strategies.  More detailed strategy-specific functionality
    is tested in individual per-strategy test files.
    """
    strat = Strategy.new('Alfa 1')
    assert isinstance(strat, StrategyRandom)
    assert strat.seed is None

    strat = Strategy.new('Alfa 2')
    assert isinstance(strat, StrategyRandom)
    assert strat.seed == 99999

    strat = Strategy.new('Bravo 1')
    assert isinstance(strat, StrategySimple)
    assert not strat.aggressive

    strat = Strategy.new('Bravo 2')
    assert isinstance(strat, StrategySimple)
    assert strat.aggressive

    strat = Strategy.new('Charlie 1')
    assert isinstance(strat, StrategySmart)
    assert not strat.hand_analysis
    assert isinstance(strat.bid_thresh, list)
    assert isinstance(strat.alone_margin, list)
    assert isinstance(strat.def_alone_thresh, list)
    assert len(strat.bid_thresh) == 8
    assert len(strat.alone_margin) == 8
    assert len(strat.def_alone_thresh) == 8

    strat = Strategy.new('Charlie 2')
    assert isinstance(strat, StrategySmart)
    assert isinstance(strat.hand_analysis, dict)
    assert isinstance(strat.bid_thresh, list)
    assert isinstance(strat.alone_margin, list)
    assert isinstance(strat.def_alone_thresh, list)
    assert len(strat.hand_analysis) == 6
    assert len(strat.bid_thresh) == 8
    assert len(strat.alone_margin) == 8
    assert len(strat.def_alone_thresh) == 8
