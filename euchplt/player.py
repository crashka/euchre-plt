#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .core import ConfigError, cfg
from .card import Card
from .euchre import Bid, Trick, DealState
from .strategy import Strategy, get_strategy

##########
# Player #
##########

class Player:
    name:     str
    strategy: Strategy

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
            self.name = name
            self.strategy = get_strategy(strategy_name)
        else:
            self.name = name
            self.strategy = strategy

    def __str__(self):
        return self.name

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """
        """
        return self.strategy.bid(deal, def_bid)

    def discard(self, deal: DealState) -> Card:
        """
        """
        return self.strategy.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """
        """
        return self.strategy.play_card(deal, trick, valid_plays)

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
