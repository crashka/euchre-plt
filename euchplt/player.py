#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional
from random import Random

from .card import SUITS, Card
from .euchre import Bid, PASS_BID, defend_suit, DealState

##########
# Player #
##########

class Player:
    """
    """
    def __init__(self):
        self.name        = None
        self.bid_class   = None
        self.bid_params  = {}
        self.play_class  = None
        self.play_params = {}

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """
        """
        raise NotImplementedError("Can't call abstract method")

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called
        """
        raise NotImplementedError("Can't call abstract method")

    def play_card(self, deal: DealState, valid_plays: list[Card]) -> Card:
        """
        """
        raise NotImplementedError("Can't call abstract method")

################
# PlayerRandom #
################

class PlayerRandom(Player):
    """
    """
    randgen: Random

    def __init__(self, seed: int = None):
        super().__init__()
        self.randgen = Random(seed)
        
    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            alone = self.randgen.random() < 0.10
            return Bid(defend_suit, alone)
        
        bid_no = len(deal.bids)
        if self.randgen.random() < 1 / (9 - bid_no):
            return PASS_BID

        if deal.bid_round == 1:
            alone = self.randgen.random() < 0.10
            return Bid(deal.turn_card.suit, alone)
        else:
            alone = self.randgen.random() < 0.20
            return Bid(self.randgen.choice(SUITS), alone)

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.randgen.choice(deal.hand.cards)

    def play_card(self, deal: DealState, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.randgen.choice(valid_plays)

#############
# PlayerMin #
#############

class PlayerMin(Player):
    """
    """
    pass

#############
# PlayerStd #
#############

class PlayerStd(Player):
    """
    """
    pass

############
# PlayerML #
############

class PlayerML(Player):
    """
    """
    pass

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
