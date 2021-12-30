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
    DEAL_COMPLETE = "Deal Complete"

##########
# Player #
##########

class Player:
    """For now, we just delegate calls to the Strategy class.  LATER: we probably
    need to rethink the design of this class (perhaps if/when we add human and/or
    network players)!!!
    """
    name:       str
    strategy:   Strategy

    disamb:     ClassVar[list[str]] = [c for c in 'abcdefghijklmnop']

    def __init__(self, name: str, strategy: Strategy = None):
        """A player maybe be defined by an entry in the config file (identified
        by `name`); or if an instantiated `strategy` object, we will create an
        ad hoc player (in which case `name` is just a label with no additional
        meaning or association)
        """
        if not strategy:
            players = cfg.config('players')
            if name not in players:
                raise RuntimeError(f"Player '{name}' is not known")
            strategy_name = players[name].get('strategy')
            if not strategy_name:
                raise ConfigError(f"'strategy' not specified for player '{name}'")
            if name[-1].isdecimal():
                name += self.disamb.pop(0)
            self.name = name
            self.strategy = Strategy.new(strategy_name)
        else:
            self.name = name
            self.strategy = strategy

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

    def notify(self, deal: DealState, notice_type: PlayerNotice) -> None:
        """TEMP: for now, we are only expecting `DEAL_COMPLETE`--LATER we will think
        about the other notifications needed to support remote players/strategies!!!
        """
        assert notice_type == PlayerNotice.DEAL_COMPLETE
        return self.strategy.notify(deal, StrategyNotice.DEAL_COMPLETE)

###############
# PlayerHuman #
###############

class PlayerHuman(Player):
    """
    """
    pass

#################
# PlayerNetwork #
#################

class PlayerNetwork(Player):
    """
    """
    pass
