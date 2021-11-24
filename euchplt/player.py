#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from .card import Card
from .euchre import Bid, PASS_BID, DealState

##########
# Player #
##########

class Player(object):
    """
    """
    def __init__(self):
        self.name        = None
        self.bid_class   = None
        self.bid_params  = {}
        self.play_class  = None
        self.play_params = {}

    def bid(self, deal_state: DealState) -> Bid:
        """
        """
        raise NotImplementedError("Can't call abstract method")

    def discard(self, deal_state: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called
        """
        raise NotImplementedError("Can't call abstract method")

    def play_card(self, deal_state: DealState, valid_plays: list[Card]) -> Card:
        """
        """
        raise NotImplementedError("Can't call abstract method")

################
# PlayerRandom #
################

class PlayerRandom(Player):
    """
    """
    def bid(self, deal_state: DealState) -> Bid:
        """See base class
        """
        return PASS_BID

    def discard(self, deal_state: DealState) -> Card:
        """See base class
        """
        return deal_state.hand[0]

    def play_card(self, deal_state: DealState, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return deal_state.hand[0]
