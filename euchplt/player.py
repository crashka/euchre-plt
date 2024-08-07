#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import ClassVar
from enum import Enum

from .core import ConfigError, cfg
from .card import Card
from .euchre import Bid, Trick, DealState
from .strategy import Strategy, StrategyNotice

#################
# Notifications #
#################

class PlayerNotice(Enum):
    BID_COMPLETE   = "Bid Complete"
    TRICK_COMPLETE = "Trick Complete"
    DEAL_COMPLETE  = "Deal Complete"
    GAME_COMPLETE  = "Game Complete"
    MATCH_COMPLETE = "Match Complete"

##########
# Player #
##########

class Player:
    """A player maybe be defined by an entry in the config file (identified by ``name``)
    or by a specified strategy (either an instantiated ``Strategy`` object or a configured
    strategy name)--in the latter case (strategy specification), the player name needs to
    unique across instantiations (though we are not currently enforcing at this level).

    For now, we just delegate calls to the ``Strategy`` class.  LATER: we probably need to
    rethink the design of this class (perhaps if/when we add human and/or remote
    players)!!!
    """
    name:       str
    strategy:   Strategy

    disamb:     ClassVar[list[str]] = [c for c in 'abcdefghijklmnop']

    def __init__(self, name: str, strategy: Strategy | str = None):
        """
        """
        if not strategy:
            players = cfg.config('players')
            if name not in players:
                raise RuntimeError(f"Player '{name}' is not known")
            strategy_name = players[name].get('strategy')
            if not strategy_name:
                raise ConfigError(f"'strategy' not specified for player '{name}'")
            # SPECIAL_CASE: convention for identifying ML data generation strategies,
            # all players for the deal will have same name, so we distinguish them
            if name[-1].isdecimal() and strategy_name == name:
                name += self.disamb.pop(0)
            self.name = name
            self.strategy = Strategy.new(strategy_name)
        elif isinstance(strategy, Strategy):
            self.name = name
            self.strategy = strategy
        else:
            # configured strategy (by strategy name)
            assert isinstance(strategy, str)
            self.name = name  # player name
            self.strategy = Strategy.new(strategy)

    def __str__(self):
        return self.name

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """Relevant context information can be found in `deal.hand`, `deal.pos`, etc.
        Note that we get called with `def_bid = True` if opponent calls a loner, to
        give us a chance to defend alone.

        Note that `deal.player_state` is a dict that the Strategy implementation may
        use to persist state between calls (opaque to the calling module)
        """
        return self.strategy.bid(deal, def_bid)

    def discard(self, deal: DealState) -> Card:
        """Only called for the dealer position if the turn card has been ordered up,
        or if the dealer chooses to pick it up.  Note that the turn card is already
        in the player's hand (six cards now) when this is called.
        """
        return self.strategy.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """TODO: should probably remove the `trick` arg, since it is always same as
        `deal.cur_trick`).

        Note that in `valid_plays`, jacks are NOT translated into bowers, and thus the
        implementation should also NOT return bowers (`card.realcard()` can be used if
        bowers are used as part of the analysis)
        """
        return self.strategy.play_card(deal, trick, valid_plays)

    def notify(self, deal: DealState, notice: PlayerNotice) -> None:
        """Pass notifications on to underlying strategies
        """
        return self.strategy.notify(deal, notice)

###############
# PlayerHuman #
###############

class PlayerHuman(Player):
    """
    """
    pass

#################
# PlayerRemote #
#################

class PlayerRemote(Player):
    """
    """
    pass
