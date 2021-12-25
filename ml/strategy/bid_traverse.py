# -*- coding: utf-8 -*-

import os
import sys
from typing import ClassVar, Optional, NamedTuple
from time import sleep

from euchplt.core import log, DEBUG
from euchplt.card import SUITS, Card
from euchplt.euchre import Bid, PASS_BID, defend_suit, Hand, Trick, DealState
from euchplt.analysis import SUIT_CTX, HandAnalysis
from euchplt.strategy import Strategy, StrategyNotice

#######################
# BidContext/Features #
#######################

class BidContext(NamedTuple):
    bid_pos:          int
    hand:             Hand
    turn_card:        Card
    bid:              Bid

class BidFeatures(NamedTuple):
    bid_pos:          int
    go_alone:         int
    turn_card_level:  int
    bid_turn_suit:    int
    bid_next_suit:    int
    bid_green_suit:   int
    top_trump_strg:   int
    top_2_trump_strg: int
    top_3_trump_strg: int
    num_trump:        int
    num_next:         int
    num_voids:        int
    num_singletons:   int
    num_off_aces:     int

class BidOutcome(NamedTuple):
    num_tricks:       int
    points:           int

###################
# BidDataAnalysis #
###################

class BidDataAnalysis(HandAnalysis):
    """
    """
    trump_values: list[int]
    deal:         DealState

    def __init__(self, deal: DealState, params: dict = None):
        super().__init__(deal.hand.copy())
        self.trump_values = params.get('trump_values')
        self.deal = deal

    def get_context(self, bid:Bid) -> BidContext:
        context = {
            'bid_pos':   self.deal.bid_pos,
            'hand':      self.hand,
            'turn_card': self.deal.turn_card,
            'bid':       bid
        }
        return BidContext._make(context.values())

    def get_features(self, bid: Bid) -> BidFeatures:
        """Comments from `ml-euchre` (need to be rethought and adapted!!!):
        Input features:
          - Bid position (0-7)
          - Loner called
          - Level of turncard (1-8)
          - Relative suit of turncard (in relation to trump)
              - One-hot encoding for next, green, or purple (all zeros if turncard
                picked up)
          - Trump (turncard or called) suit strength (various measures, start with
            sum of levels 1-8)
              - Top 1, 2, and 3 trump cards (three aggregate values)
              - Note: include turncard and exclude discard, if dealer (which implies
                that model will be tied to discard algorithm)
          - Trump/next/green/purple suit scores (instead of just trump strength?)
          - Number of trump (with turncard/discard, if dealer)
          - Number of voids (or suits)
          - Number of off-aces
        Output feature(s):
          - Number of tricks taken
        """
        turn_card   = self.deal.turn_card
        turn_suit   = turn_card.suit
        next_suit   = turn_suit.next_suit()
        green_suits = turn_suit.green_suits()

        trump_cards = self.trump_cards(bid.suit)
        trump_strgs = [0] * 5
        for i, card in enumerate(trump_cards):
            card_value = self.trump_values[card.rank.idx]
            for j in range(i, 5):
                trump_strgs[j] += card_value

        # CONSIDER: should we also compute top 1-2 values for next and green
        # suits as well???

        features = {
            'bid_pos':          self.deal.bid_pos,
            'go_alone':         int(bid.alone),
            'turn_card_level':  turn_card.efflevel(SUIT_CTX[turn_suit]),
            'bid_turn_suit':    int(bid.suit == turn_suit),
            'bid_next_suit':    int(bid.suit == next_suit),
            'bid_green_suit':   int(bid.suit in green_suits),
            'top_trump_strg':   trump_strgs[0],
            'top_2_trump_strg': trump_strgs[1],
            'top_3_trump_strg': trump_strgs[2],
            'num_trump':        len(trump_cards),
            'num_next':         len(self.next_suit_cards(bid.suit)),
            'num_voids':        len(self.voids(bid.suit)),
            'num_singletons':   len(self.singleton_cards(bid.suit)),
            'num_off_aces':     len(self.off_aces(bid.suit))
        }
        return BidFeatures._make(features.values())

#######################
# StrategyBidTraverse #
#######################

NUM_PLAYERS   = 4
BID_POSITIONS = 8

class StrategyBidTraverse(Strategy):
    """Run though each deal with all possible bids, playing out the hands
    using the specified strategy.  Append results (bid features and deal
    outcome) to training data set.
    """
    play_strat:      Strategy
    discard_strat:   Optional[Strategy]
    bid_prune_strat: Optional[Strategy]
    hand_analysis:   dict
    child_pids:      list[int]         = None
    bid_context:     BidContext
    bid_features:    BidFeatures
    bid_outcome:     BidOutcome
    my_bid:          Bid               = None

    bid_pos:         ClassVar[int]     = None

    def __init__(self, **kwargs):
        """This class recognizes the following parameters (passed in directly as
        as kwargs, or specified in the config file, if using `Strategy.new()`):

          - `play_strat` (passed in as either an instantiated `Strategy` object or
            a named configuration) is used to play out deals for each bid traversal
            selection.

          - `discard_stat` (again, object or config name) is used to determine the
            discard for each bid selection (considered part of the "play" process,
            for purposes of bid model training, even in the case of the first round
            dealer bid).  If not specified, the `play_strat` instance will be used.

          - `bid_prune_strat` (object or config name) is used to determine whether
            a preemptive bid would issued (rather than dutifully passing) prior to
            reaching the target bid position.  If so, then this bid traversal
            instance is eliminated, which will prevent a errant/misleading playing
            out of a target bid, since it would be facing an unrealistically strong
            opposition.  If this parameter is not specified, then no pruning occurs,
            and the target bid is always played out and recorded.  Note that pruning
            using a fairly aggressive bidding strategy has the unfortunate side
            effect of requiring many more cycles to generate sufficient data for
            later (especially second round) bidding positions.
        """
        super().__init__(**kwargs)
        if not self.play_strat:
            raise ConfigError("'play_strat' must be specified")
        if isinstance(self.play_strat, str):
            self.play_strat = Strategy.new(self.play_strat)
        if not isinstance(self.play_strat, Strategy):
            raise ConfigError("'play_strat' must resolve to a Strategy subclass")

        if self.discard_strat:
            if isinstance(self.discard_strat, str):
                self.discard_strat = Strategy.new(self.discard_strat)
            if not isinstance(self.discard_strat, Strategy):
                raise ConfigError("'discard_strat' must resolve to a Strategy subclass")

        if self.bid_prune_strat:
            if isinstance(self.bid_prune_strat, str):
                self.bid_prune_strat = Strategy.new(self.bid_prune_strat)
            if not isinstance(self.bid_prune_strat, Strategy):
                raise ConfigError("'bid_prune_strat' must resolve to a Strategy subclass")

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

        if deal.bid_pos != self.bid_pos:
            if self.bid_prune_strat:
                bid = self.bid_prune_strat.bid(deal)
                if not bid.is_pass():
                    log.debug(f"Aborting traverse for bid_pos {self.bid_pos}, "
                              f"preemptive bid ({bid}) from bid_pos {deal.bid_pos}")
                    exit(0)
            return PASS_BID

        if deal.bid_round == 1:
            self.my_bid = Bid(deal.turn_card.suit, alone)
            analysis = BidDataAnalysis(deal, self.hand_analysis)
            self.bid_context = analysis.get_context(self.my_bid)
            self.bid_features = analysis.get_features(self.my_bid)
            return self.my_bid
        else:
            assert deal.bid_round == 2
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
            analysis = BidDataAnalysis(deal, self.hand_analysis)
            self.bid_context = analysis.get_context(self.my_bid)
            self.bid_features = analysis.get_features(self.my_bid)
            return self.my_bid

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        if not self.discard_strat:
            return self.play_strat.discard(deal)
        return self.discard_strat.discard(deal)

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

        self.bid_outcome = BidOutcome(deal.my_tricks_won, deal.my_points)
        self.bid_context.hand.cards.sort(key=lambda c: c.sortkey)

        log.debug(', '.join(f"{k}: {v}" for k, v in self.bid_context._asdict().items()))
        log.debug(list(self.bid_features) + list(self.bid_outcome))
        all_features = list(self.bid_features) + list(self.bid_outcome)
        features_str = '\t'.join(str(x) for x in all_features)
        # HACK: see comments in bid_data.py!
        if data_file := os.environ.get('BID_DATA_FILE'):
            with open(data_file, 'a') as f:
                print(features_str, file=f)
        else:
            print(features_str)

        if self.bid_pos == 0:
            # need to reset the class, so this works for the next deal
            StrategyBidTraverse.bid_pos = None
            self.child_pids             = None
            self.my_bid                 = None
        else:
            # if we spawned the process, we need to terminate it, so it doesn't continue
            # processing downstream outside of our purview
            sys.exit(0)
