# -*- coding: utf-8 -*-

from ..card import Card
from ..euchre import Bid, Trick, DealState
from .base import Strategy, StrategyNotice

##################
# StrategyHybrid #
##################

class StrategyHybrid(Strategy):
    """Implement a hybrid strategy based on other configured strategies.  Mixed strategy
    subclasses are supported for the various aspects (bid, discard, and play).  If the
    discard strategy is not specified, the bidding strategy will be called.  Later, we may
    support parameters overrides for the subordinate strategies (though that may be
    overkill, and not needed).
    """
    # config parameters
    bid_strategy:     str
    discard_strategy: str
    play_strategy:    str
    # instance variables
    bid_inst:         Strategy
    discard_inst:     Strategy
    play_inst:        Strategy

    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)
        self.bid_inst  = Strategy.new(self.bid_strategy)
        self.play_inst = Strategy.new(self.play_strategy)
        if self.discard_strategy:
            self.discard_inst = Strategy.new(self.discard_strategy)
        else:
            self.discard_inst = self.bid_inst

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        return self.bid_inst.bid(deal, def_bid)

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.discard_inst.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.play_inst.play_card(deal, trick, valid_plays)

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """See base class
        """
        # LATER: figure out whether/which subordinate strategies and methods need
        # notifications passed through!!!
        pass
