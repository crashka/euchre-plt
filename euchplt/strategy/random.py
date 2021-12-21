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
    """
    """
    seed:   Optional[int] = None
    random: Random

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.random = Random(self.seed)

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
