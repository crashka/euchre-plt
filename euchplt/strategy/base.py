# -*- coding: utf-8 -*-

from enum import Enum
from importlib import import_module

from ..core import ConfigError, cfg
from ..card import Card
from ..euchre import Bid, Trick, DealState

#################
# Notifications #
#################

class StrategyNotice(Enum):
    """Notification type for the ``notify()`` call
    """
    DEAL_COMPLETE = "Deal Complete"

############
# Strategy #
############

class Strategy:
    """Abstract base class, cannot be instantiated directly.  Subclasses should be
    instantiated using ``Strategy.new(<strat_name>).``

    Subclasses must implement the following methods:

    - ``bid()``
    - ``discard()``
    - ``play_card()``
    - ``notify()`` – *[optional]* handle notifications (e.g. ``DEAL_COMPLETE``)

    The context for all calls is provided by `DealState`, which is defined as follows (in
    euchre.py).
    """
    @classmethod
    def new(cls, strat_name: str, **kwargs) -> 'Strategy':
        """Return instantiated Strategy object based on configured strategy, identified
        by name; note that the named strategy entry may override base parameter values
        specified for the underlying implementation class
        """
        strategies = cfg.config('strategies')
        if strat_name not in strategies:
            raise RuntimeError(f"Strategy '{strat_name}' is not known")
        strat_info   = strategies[strat_name]
        class_name   = strat_info.get('base_class')
        module_path  = strat_info.get('module_path')
        strat_params = strat_info.get('strategy_params') or {}
        if not class_name:
            raise ConfigError(f"'base_class' not specified for strategy '{strat_name}'")
        if module_path:
            module = import_module(module_path)
            strat_class = getattr(module, class_name)
        else:
            strat_class = globals()[class_name]
        if not issubclass(strat_class, cls):
            raise ConfigError(f"'{strat_class.__name__}' not subclass of '{cls.__name__}'")

        for key, value in kwargs.items():
            # NOTE: this is a shallow override--caller has to guard against non-empty
            # lists/dicts with sparse or empty entries!
            if value:
                strat_params[key] = value

        return strat_class(**strat_params)

    def __init__(self, **kwargs):
        """Note that kwargs are parameters overrides on top of base_strategy_params
        (in the config file) for the underlying implementation class
        """
        class_name = type(self).__name__
        base_params = cfg.config('base_strategy_params')
        if class_name not in base_params:
            raise ConfigError(f"Strategy class '{class_name}' does not exist")
        for key, base_value in base_params[class_name].items():
            setattr(self, key, kwargs.get(key) or base_value)
        pass  # TEMP: for debugging!!!

    def __str__(self):
        return type(self).__name__

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """Note that ``deal`` contains a dict element named ``player_state``, which the
        implementation may use to persist state between calls (opaque to the calling
        module)
        """
        raise NotImplementedError("Can't call abstract method")

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called
        """
        raise NotImplementedError("Can't call abstract method")

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """TODO: should probably remove ``trick`` as an arg (always same as
        ``deal.cur_trick``)

        Note that in ``valid_plays`` (arg), jacks are NOT translated into bowers, and thus
        the implementation should also NOT return bowers (``card.realcard()`` can be used
        if bowers are utilized as part of the analysis and/or strategy)
        """
        raise NotImplementedError("Can't call abstract method")

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """Subclasses do not have to implement this (or call ``super()`` for it); only
        specialty strategies need to know when intermediary milestones are hit (e.g. to
        notify servers representing ``StrategyRemote`` players, or to support "traversal"
        strategies for ML data generation).
        """
        # do nothing
        pass
