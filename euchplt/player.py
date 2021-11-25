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
    random: Random

    def __init__(self, seed: int = None):
        super().__init__()
        self.random = Random(seed)
        
    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            alone = self.random.random() < 0.10
            return Bid(defend_suit, alone)
        
        bid_no = len(deal.bids)
        do_bid = self.random.random() < 1 / (9 - bid_no)
        if do_bid:
            if deal.bid_round == 1:
                alone = self.random.random() < 0.10
                return Bid(deal.turn_card.suit, alone)
            else:
                alone = self.random.random() < 0.20
                biddable_suits = [s for s in SUITS if s != deal.turn_card.suit]
                return Bid(self.random.choice(biddable_suits), alone)
        else:
            return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.random.choice(deal.hand.cards)

    def play_card(self, deal: DealState, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.random.choice(valid_plays)

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
