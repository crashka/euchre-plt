# -*- coding: utf-8 -*-

from .base import Strategy, StrategyNotice
from .random import StrategyRandom
from .simple import StrategySimple
from .smart import StrategySmart
from .ml import StrategyML
# for sphinx
from .__main__ import tune_strategy_smart, main
