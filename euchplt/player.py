#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .card import Card
from .euchre import Bid, Trick, DealState
from .strategy import Strategy, StrategyRandom

##########
# Player #
##########

class Player:
    name:     str
    strategy: Strategy

    def __init__(self, name: str, strategy_cls: type = StrategyRandom, **kwargs):
        self.name     = name
        self.strategy = strategy_cls(**kwargs)

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
