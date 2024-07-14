# -*- coding: utf-8 -*-

from ..card import Card
from ..euchre import Bid, PASS_BID, Trick, DealState
from .base import Strategy

##################
# StrategyRandom #
##################

class StrategyRemote(Strategy):
    """
    """
    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return deal.hand.cards[0]

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return valid_plays[0]
