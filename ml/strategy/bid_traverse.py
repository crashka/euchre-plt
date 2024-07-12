# -*- coding: utf-8 -*-

import os
import os.path
import sys
import queue
from typing import ClassVar, Optional, NamedTuple, TextIO
from multiprocessing.queues import Queue
import multiprocessing as mp

from euchplt.core import log, ConfigError
from euchplt.card import SUITS, Card
from euchplt.euchre import Bid, PASS_BID, NULL_BID, DEFEND_ALONE, defend_suit
from euchplt.euchre import Trick, DealState
from euchplt.analysis import SUIT_CTX, HandAnalysis
from euchplt.strategy import Strategy, StrategyNotice

#######################
# BidFeatures/Outcome #
#######################

class BidFeatures(NamedTuple):
    """
    """
    bid_pos:          int
    go_alone:         int
    def_alone:        int
    def_pos_rel:      int  # relative to bid_pos: 1 or 3
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
    """
    """
    num_tricks:       float
    points:           float

###################
# BidDataAnalysis #
###################

NUM_PLAYERS   = 4
BID_POSITIONS = 8

class BidDataAnalysis(HandAnalysis):
    """
    """
    trump_values: list[int]
    deal:         DealState

    def __init__(self, deal: DealState, **kwargs):
        """
        """
        super().__init__(deal.hand.copy())
        self.trump_values = kwargs.get('trump_values')
        self.deal = deal

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
        deal        = self.deal
        turn_card   = deal.turn_card
        turn_suit   = turn_card.suit
        next_suit   = turn_suit.next_suit()
        green_suits = turn_suit.green_suits()
        if bid.suit != defend_suit:
            trump_suit  = bid.suit
            go_alone    = bid.alone
            def_alone   = False
            bid_pos     = deal.bid_pos
            def_pos_rel = 0
        else:
            trump_suit  = deal.contract.suit
            go_alone    = deal.contract.alone
            def_alone   = True
            # note that `deal.bid_round` (in its current form)
            # doesn't work here
            bid_round   = 1 if trump_suit == turn_suit else 2
            bid_pos     = deal.caller_pos + (bid_round - 1) * 4
            def_pos_rel = deal.bid_pos - bid_pos

        trump_cards = self.trump_cards(trump_suit)
        trump_strgs = [0] * 5
        for i, card in enumerate(trump_cards):
            card_value = self.trump_values[card.rank.idx]
            for j in range(i, 5):
                trump_strgs[j] += card_value

        # CONSIDER: should we also compute top 1-2 values for next and green
        # suits as well???

        features = {
            'bid_pos'         : bid_pos,
            'go_alone'        : int(go_alone),
            'def_alone'       : int(def_alone),
            'def_pos_rel'     : def_pos_rel,
            'turn_card_level' : turn_card.efflevel(SUIT_CTX[turn_suit]),
            'bid_turn_suit'   : int(trump_suit == turn_suit),
            'bid_next_suit'   : int(trump_suit == next_suit),
            'bid_green_suit'  : int(trump_suit in green_suits),
            'top_trump_strg'  : trump_strgs[0],
            'top_2_trump_strg': trump_strgs[1],
            'top_3_trump_strg': trump_strgs[2],
            'num_trump'       : len(trump_cards),
            'num_next'        : len(self.next_suit_cards(trump_suit)),
            'num_voids'       : len(self.voids(trump_suit)),
            'num_singletons'  : len(self.singleton_cards(trump_suit)),
            'num_off_aces'    : len(self.off_aces(trump_suit))
        }
        return BidFeatures._make(features.values())

#######################
# StrategyBidTraverse #
#######################

class StrategyBidTraverse(Strategy):
    """Run though each deal with all possible bids, playing out the hands
    using the specified strategy.  Append results (bid features and deal
    outcome) to training data set.
    """
    play_strat:      Strategy
    discard_strat:   Optional[Strategy]
    bid_prune_strat: Optional[Strategy]
    hand_analysis:   dict

    bid_features:    BidFeatures       = None
    bid_outcome:     BidOutcome        = None
    child_pids:      list[int]         = None
    my_bid:          Bid               = None

    bid_pos:         ClassVar[int]     = None  # 0-7 (factors in bidding round)
    alone:           ClassVar[bool]    = False
    def_pos:         ClassVar[int]     = None  # defend-alone bid position (1-10)
    queue:           ClassVar[Queue]   = None

    def __init__(self, **kwargs):
        """This class recognizes the following parameters (passed in directly as
        as kwargs, or specified in the config file, if using `Strategy.new()`):

        - `play_strat` (passed in as either an instantiated `Strategy` object or
          a named configuration) is used to play out deals for each bid traversal
          selection.

        - `discard_strat` (again, object or config name) is used to determine the
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

    def _reset(self) -> None:
        """Put both the instance and class variables back to initial state
        """
        self.bid_features           = None
        self.bid_outcome            = None
        self.child_pids             = None
        self.my_bid                 = None
        StrategyBidTraverse.bid_pos = None
        StrategyBidTraverse.alone   = False
        StrategyBidTraverse.def_pos = None
        StrategyBidTraverse.queue   = None

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            if deal.bid_pos == self.def_pos:
                assert deal.contract
                assert deal.go_alone
                self.my_bid = DEFEND_ALONE
                analysis = BidDataAnalysis(deal, **self.hand_analysis)
                self.bid_features = analysis.get_features(self.my_bid)
                return self.my_bid
            return NULL_BID

        if self.bid_pos is None:
            # see PERF NOTE in `notify()` below
            StrategyBidTraverse.queue = mp.Queue()
            # Spawn subprocesses to handle positions 1-7, we will fallthrough
            # the loop and handle the 0th position ourselves; take that end of
            # the sequence to avoid spawning both here and in the second round
            # "7th" position, as well as ensuring that we don't abort due to a
            # preemptive pruning bid
            child_pids = []
            for i in range(1, BID_POSITIONS):
                child_pid = os.fork()
                if child_pid == 0:
                    StrategyBidTraverse.bid_pos = i
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
                    # Note that this is not a real bid, just what the prune strategy
                    # *would* have bid; it is important that we can't get here from
                    # the main proc, since that would terminate the entire traversal
                    assert self.bid_pos != 0
                    log.debug(f"Aborting traverse for bid_pos {self.bid_pos}, "
                              f"preemptive bid ({bid}) from bid_pos {deal.bid_pos}")
                    self.queue.close()
                    os._exit(0)
            return PASS_BID

        bid_suit = None
        if deal.bid_round == 1:
            bid_suit = deal.turn_card.suit
        else:
            assert deal.bid_round == 2
            # Spawn subprocesses to handle the first two of the three non-
            # turn suits for this round, we will fallthrough the loop and
            # handle the remaining suit ourselves
            child_pids = []
            biddable_suits = [s for s in SUITS if s != deal.turn_card.suit]
            for suit in biddable_suits[:-1]:
                child_pid = os.fork()
                if child_pid == 0:
                    bid_suit = suit
                    break
                child_pids.append(child_pid)
            else:
                bid_suit = biddable_suits[-1]
                assert self.child_pids is None
                self.child_pids = child_pids
        assert bid_suit in SUITS

        # For all biddable cases, we spawn three additional subprocesses for
        # going alone: for defending together, and for defending alone in each
        # of the opposing positions
        child_pids = []
        for def_pos_rel in [None, 1, 3]:
            child_pid = os.fork()
            if child_pid == 0:
                self.child_pids = None
                StrategyBidTraverse.alone = True
                if def_pos_rel:
                    # note that this is a bid position (1-10), not a deal position
                    StrategyBidTraverse.def_pos = self.bid_pos + def_pos_rel
                else:
                    assert self.def_pos is None
                break
            child_pids.append(child_pid)
        else:
            assert not self.alone
            assert self.def_pos is None
            if self.child_pids is None:
                self.child_pids = child_pids
            else:
                self.child_pids.extend(child_pids)

        # When going alone, don't account the defend-alone outcomes for the
        # calling hand's features, since that would skew the results; those
        # cases are purely for the defend-alone model(s)
        if self.alone and self.def_pos:
            assert not self.child_pids
            return Bid(bid_suit, self.alone)

        # Now (finally!) we can compute our features and return our bid
        self.my_bid = Bid(bid_suit, self.alone)
        analysis = BidDataAnalysis(deal, **self.hand_analysis)
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
            hdr = f"pid {os.getpid()} bid_pos {self.bid_pos} bid {self.my_bid.suit}:"
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
        my_features = list(self.bid_features) + list(self.bid_outcome)

        # PERF NOTE: it is actually ~10% slower to funnel bid data to the master
        # process (`self.bid_pos = 0`), rather than let all bidders just append
        # to the data file themselves (due to the additional synchronization),
        # but we do it this way for the better integrity
        def dequeue_print(file: TextIO = sys.stdout) -> None:
            try:
                while True:
                    features = self.queue.get_nowait()
                    features_str = '\t'.join(str(x) for x in features)
                    print(features_str, file=file)
            except queue.Empty:
                pass

        # FIX: this implicitly identifies the main process (based on knowledge
        # of current implementation in `bid()`); would definitely be better to
        # make this explicit (as in `play_traverse.py`)!!!
        if self.bid_pos == 0 and not self.alone:
            # HACK: see comments in bid_data.py!
            if data_file := os.environ.get('BID_DATA_FILE'):
                if not os.path.exists(data_file):
                    header = BidFeatures._fields + BidOutcome._fields
                    header_str = '\t'.join(header)
                else:
                    header_str = None
                my_features_str = '\t'.join(str(x) for x in my_features)
                with open(data_file, 'a') as f:
                    if header_str:
                        print(header_str, file=f)
                    print(my_features_str, file=f)
                    dequeue_print(f)
            else:
                header = BidFeatures._fields + BidOutcome._fields
                header_str = '\t'.join(header)
                my_features_str = '\t'.join(str(x) for x in my_features)
                print(header_str)
                print(my_features_str)
                dequeue_print()

            # need to reset the class, so this works for the next deal
            self._reset()
        else:
            self.queue.put(my_features)
            self.queue.close()
            self.queue.join_thread()
            # if we spawned the process, we need to terminate it, so it doesn't continue
            # processing downstream outside of our purview
            os._exit(0)
