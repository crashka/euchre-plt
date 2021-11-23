#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from .card import Card
from .euchre import Bid, PASS_BID

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

    def bid(self, deal_state: dict) -> Bid:
        return PASS_BID

    def pick_up(self, deal_state: dict) -> Optional[Card]:
        """Return the discard
        """
        return None
