# -*- coding: utf-8 -*-

from typing import Optional
from random import Random

from ..card import SUITS, Card
from ..euchre import Bid, PASS_BID, defend_suit, Trick, DealState
from .base import Strategy

##################
# StrategyRandom #
##################

class StrategyRandom(Strategy):
    """Randomly pick between valid bids, discards, and card plays.  Note that there are a
    number of magic numbers hardwired into the implementation (e.g. thresholds for whether
    or when to bid, go/defend alone, etc.), which we may want to parameterize for some
    visibility (this is, after all, a teaching tool).
    """
    rand_seed: Optional[int]
    random:    Random

    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)
        self.random = Random(self.rand_seed or id(self))

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            alone = self.random.random() < 0.10
            return Bid(defend_suit, alone)

        bid_num = len(deal.bids)
        do_bid = self.random.random() < 1 / (9 - bid_num)
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

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.random.choice(valid_plays)
