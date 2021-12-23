# -*- coding: utf-8 -*-

import os
from typing import ClassVar
from time import sleep

from ..core import log
from ..card import SUITS, Card
from ..euchre import Bid, PASS_BID, defend_suit, Trick, DealState
from .base import Strategy, StrategyNotice

##################
# StrategyRandom #
##################

NUM_PLAYERS   = 4
BID_POSITIONS = 8

class StrategyBidTraverse(Strategy):
    """Run though each deal with all possible bids, playing out the hands
    using the specified strategy.  Append results (bid features and deal
    outcome) to training data set.
    """
    play_strat: Strategy
    child_pids: list[int]     = None
    my_bid:     Bid           = None
    bid_pos:    ClassVar[int] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        pass

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        alone = False  # default for both regular and defensive bidding

        if def_bid:
            # TEMP: for now we won't hit this, since we're not traversing
            # loner bids right now (LATER may be added into this class or
            # possibly broken out into separate implementation)
            assert False

        if self.bid_pos is None:
            # Spawn subprocesses to handle positions 1-7, we will fallthrough
            # the loop and handle the 0th position ourselves (take that end of
            # the sequence to avoid spawning both here and in the second round
            # "7th" position, otherwise we would have to manage `child_pids`
            # as a class variable)
            child_pids = []
            for i in range(1, BID_POSITIONS):
                StrategyBidTraverse.bid_pos = i
                child_pid = os.fork()
                if child_pid == 0:
                    break
                child_pids.append(child_pid)
            else:
                StrategyBidTraverse.bid_pos = 0
                assert self.child_pids is None
                self.child_pids = child_pids

        cur_bid_pos = deal.pos + (deal.bid_round - 1) * 4
        if cur_bid_pos != self.bid_pos:
            return PASS_BID

        if deal.bid_round == 1:
            self.my_bid = Bid(deal.turn_card.suit, alone)
            return self.my_bid
        else:
            # Spawn subprocesses to handle the first two of the three non-
            # turn suits for this round, we will fallthrough the loop and
            # handle the remaining suit ourselves
            child_pids = []
            biddable_suits = [s for s in SUITS if s != deal.turn_card.suit]
            for bid_suit in biddable_suits[:-1]:
                child_pid = os.fork()
                if child_pid == 0:
                    break
                child_pids.append(child_pid)
            else:
                bid_suit = biddable_suits[-1]
                assert self.child_pids is None
                self.child_pids = child_pids

            self.my_bid = Bid(bid_suit, alone)
            return self.my_bid

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.play_strat.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.play_strat.play_card(deal, trick, valid_plays)

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """Write feature set based on traversal on `DEAL_COMPLETE` notification,
        also ensure that child processes completed successfully
        """
        if not self.my_bid:
            return

        if self.child_pids:
            hdr = f"pid {os.getpid()} bod_pos {self.bid_pos} bid {self.my_bid.suit}:"
            child_errs = []
            try:
                log.debug(f"{hdr} waiting on child pids: {self.child_pids}")
                while len(self.child_pids) > 0:
                    status = os.waitpid(-1, 0)
                    log.debug(f"{hdr} reaped child pid {status[0]} status {status[1]}")
                    self.child_pids.remove(status[0])
                    if status[1] != 0:
                        child_errs.append(status)
            except ChildProcessError as e:
                log.debug(f"{hdr} caught ChildProcessError: {e}")
            if child_errs:
                raise RuntimeError(f"{hdr} error(s) in child processes: {child_errs}")

        # TODO: write deal features here!!!
