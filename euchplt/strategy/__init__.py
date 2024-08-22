# -*- coding: utf-8 -*-

"""This module provides classes that implement bidding and playing strategies for players
and teams.  Note that ``Strategy`` (abstract base class) can also be subclassed by other
modules for special purpose use (see ``ml`` module).
"""

from .base import Strategy, StrategyNotice
from .random import StrategyRandom
from .simple import StrategySimple
from .smart import StrategySmart, _PlayCard
from .remote import StrategyRemote
from .hybrid import StrategyHybrid
from .ml import StrategyML
from . import priv
# for sphinx
from .__main__ import tune_strategy_smart, main
