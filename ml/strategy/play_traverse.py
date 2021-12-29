# -*- coding: utf-8 -*-

import os
import sys
import queue
from typing import NamedTuple, Optional, TextIO
from multiprocessing.queues import Queue
import multiprocessing as mp

from euchplt.core import log, DEBUG, ConfigError
from euchplt.card import Card, ace
from euchplt.euchre import Hand, Bid, Trick, DealState
from euchplt.analysis import SUIT_CTX, PlayAnalysis
from euchplt.strategy import Strategy, StrategyNotice
from .bid_traverse import BidFeatures, BidDataAnalysis

########################
# PlayContext/Features #
########################

class PlayContext(NamedTuple):
    trick_num:        int
    play_seq:         int
    cur_trick:        Trick
    cur_hand:         Hand
    valid_plays:      list[Card]
    turn_card:        Card
    contract:         Bid
    play_card:        Card

class PlayFeatures(NamedTuple):
    # context features
    trick_num:        int
    play_seq:         int
    pos:              int  # 0 = first bid, 3 = dealer
    partner_winning:  int
    lead_trumped:     int
    tricks_won:       int
    trumps_seen:      int
    turn_seen:        int
    next_seen:        int  # same color as turn
    aces_seen:        int
    # contract features
    caller_pos:       int  # 0-7 relative to first bid
    go_alone:         int
    def_alone:        int
    def_pos:          int
    turn_card_level:  int
    bid_turn_suit:    int
    bid_next_suit:    int
    bid_green_suit:   int
    # starting hand features
    top_trump_strg:   int
    top_2_trump_strg: int
    top_3_trump_strg: int
    num_trump:        int
    num_next:         int
    num_voids:        int
    num_singletons:   int
    num_off_aces:     int
    # current hand features
    cur_top_trump_strg: int
    cur_top_2_trump_strg: int
    cur_top_3_trump_strg: int
    cur_num_trump:    int
    cur_num_aces:     int
    higher_trump:     int  # higher trump outstanding
    # card to play features
    lead_winner:      int
    lead_high:        int
    lead_low:         int
    lead_trump:       int
    lead_turn:        int
    lead_next:        int
    follow_winner:    int
    follow_high:      int
    follow_low:       int
    over_trump:       int
    trump_high:       int
    trump_low:        int
    throw_off_void:   int
    throw_off_long:   int
    throw_off_low:    int
    throw_off_next:   int

class PlayOutcome(NamedTuple):
    num_tricks:       int
    points:           int

####################
# PlayDataAnalysis #
####################

class PlayDataAnalysis(PlayAnalysis):
    """Manage features for generating data for "play" ML models
    """
    trump_values: list[int]
    valid_plays:  list[Card]
    bid_features: BidFeatures
    
    def __init__(self, deal: DealState, **kwargs):
        super().__init__(deal)
        self.trump_values = kwargs.get('trump_values')
        self.valid_plays  = kwargs.get('valid_plays')
        self.bid_features = kwargs.get('bid_features')

    def get_context(self, card: Card) -> PlayContext:
        deal = self.deal

        context = {
            'trick_num'  : deal.trick_num,
            'play_seq'   : deal.play_seq,
            'cur_trick'  : deal.cur_trick,
            'cur_hand'   : deal.hand.copy(),
            'valid_plays': self.valid_plays,
            'turn_card'  : deal.turn_card,
            'contract'   : deal.contract,
            'play_card'  : card
        }
        return PlayContext._make(context.values())

    def get_features(self, card: Card) -> PlayFeatures:
        deal        = self.deal
        # context stuff
        trump_suit  = deal.contract.suit
        turn_card   = deal.turn_card
        turn_suit   = turn_card.effsuit(self.ctx)
        next_suit   = turn_suit.next_suit()
        green_suits = turn_suit.green_suits()
        off_aces    = [p[1] for t in deal.tricks
                       for p in t.plays if p[1].rank == ace and p[1].suit != trump_suit]
        # current hand stuff
        trump_cards = self.trump_cards()
        trump_strgs = [0] * 5
        if trump_cards:
            for i, card in enumerate(trump_cards):
                card_value = self.trump_values[card.rank.idx]
                for j in range(i, 5):
                    trump_strgs[j] += card_value
            higher_trump = [c for c in self.trumps_missing() if c.level > trump_cards[0].level]
        else:
            higher_trump = self.trumps_missing()
        # card to play stuff
        effcard        = card.effcard(self.ctx)
        card_suit      = card.effsuit(self.ctx)
        card_is_trump  = card_suit == trump_suit
        my_suit_cards  = self.get_suit_cards()[card_suit]
        low_level      = self.cards_by_level()[-1].level
        leading        = deal.play_seq == 0
        if not leading:
            lead_card     = deal.cur_trick.plays[0][1]
            lead_suit     = lead_card.effsuit(deal.cur_trick)
            winning_card  = deal.cur_trick.winning_card
            beats_winning = card.beats(winning_card, deal.cur_trick),
            following     = card_suit == lead_suit and not card_is_trump
            trumping      = not deal.lead_trumped and card_is_trump
            throwing_off  = deal.lead_trumped and not card_is_trump
        else:
            winning_card  = None
            beats_winning = None
            following     = False
            trumping      = False
            throwing_off  = False
        # only set `long_suit` if uniquely long (the idea is to track intent)
        suits = sorted(self.get_suit_cards().items(), key=lambda s: len(s[1]))
        long_suit = suits[-1][0] if len(suits[-2][1]) != len(suits[-1][1]) else None

        features = {
            # context features
            'trick_num'       : deal.trick_num,
            'play_seq'        : deal.play_seq,
            'pos'             : deal.pos,
            'partner_winning' : int(deal.partner_winning),
            'lead_trumped'    : int(not leading and deal.lead_trumped),
            'tricks_won'      : len(deal.tricks_won),
            'trumps_seen'     : len(deal.played_by_suit[trump_suit]),
            'turn_seen'       : len(deal.played_by_suit[turn_suit]),
            'next_seen'       : len(deal.played_by_suit[next_suit]),
            'aces_seen'       : len(off_aces),
            # contract features
            'caller_pos'      : deal.caller_pos,  # 0-7 relative to init bidder
            'go_alone'        : int(deal.go_alone),         # cannot be None???
            'def_alone'       : int(bool(deal.def_alone)),  # can be None
            'def_pos'         : -1 if deal.def_pos is None else deal.def_pos,
            'turn_card_level' : turn_card.efflevel(SUIT_CTX[turn_suit]),
            'bid_turn_suit'   : int(trump_suit == turn_suit),
            'bid_next_suit'   : int(trump_suit == next_suit),
            'bid_green_suit'  : int(trump_suit in green_suits),
            # starting hand features
            'top_trump_strg'  : self.bid_features.top_trump_strg,
            'top_2_trump_strg': self.bid_features.top_2_trump_strg,
            'top_3_trump_strg': self.bid_features.top_3_trump_strg,
            'num_trump'       : self.bid_features.num_trump,
            'num_next'        : self.bid_features.num_next,
            'num_voids'       : self.bid_features.num_voids,
            'num_singletons'  : self.bid_features.num_singletons,
            'num_off_aces'    : self.bid_features.num_off_aces,
            # current hand features
            'cur_top_trump_strg' : trump_strgs[0],
            'cur_top_2_trump_strg': trump_strgs[1],
            'cur_top_3_trump_strg': trump_strgs[2],
            'cur_num_trump'   : len(trump_cards),
            'cur_num_aces'    : len(self.off_aces()),
            'higher_trump'    : len(higher_trump),
            # card to play features
            'lead_winner'     : int(leading and card in self.my_winners()),
            'lead_high'       : int(leading and effcard == my_suit_cards[0]),
            'lead_low'        : int(leading and effcard == my_suit_cards[-1]),
            'lead_trump'      : int(leading and card_suit == trump_suit),
            'lead_next'       : int(leading and card_suit == turn_suit),
            'lead_turn'       : int(leading and card_suit == next_suit),
            'follow_winner'   : int(following and card in self.my_winners()),
            'follow_high'     : int(following and effcard == my_suit_cards[0]),
            'follow_low'      : int(following and effcard == my_suit_cards[-1]),
            'over_trump'      : int(trumping and deal.lead_trumped and beats_winning),
            'trump_high'      : int(trumping and effcard == trump_cards[0]),
            'trump_low'       : int(trumping and effcard == trump_cards[-1]),
            'throw_off_void'  : int(throwing_off and effcard in self.singleton_cards()),
            'throw_off_long'  : int(throwing_off and card_suit == long_suit),
            'throw_off_low'   : int(throwing_off and card.level == low_level),
            'throw_off_next'  : int(throwing_off and card_suit == next_suit)
        }
        return PlayFeatures._make(features.values())

########################
# StrategyPlayTraverse #
########################

NUM_PLAYERS = 4

class StrategyPlayTraverse(Strategy):
    """Run though each deal with all possible bids, playing out the hands
    using the specified strategy.  Append results (bid features and deal
    outcome) to training data set.
    """
    bid_strat:       Strategy
    discard_strat:   Optional[Strategy]
    base_play_strat: Strategy
    hand_analysis:   dict
    play_analysis:   dict

    bid_features:    BidFeatures  = None
    play_context:    PlayContext  = None
    play_features:   PlayFeatures = None
    play_outcome :   PlayOutcome  = None
    main_proc:       bool         = False
    child_pids:      list[int]    = None
    my_plays:        list[Card]   = None
    queue:           Queue        = None

    def __init__(self, **kwargs):
        """This class recognizes the following parameters (passed in directly as
        as kwargs, or specified in the config file, if using `Strategy.new()`):

          - `bid_strat` (passed in as either an instantiated `Strategy` object or
            a named configuration) is used to do the initial bidding to set the
            contract for the play traversal process.

          - `discard_stat` (again, object or config name) is used to determine the
            dealer discard in the case of first-round bids (considered part of the
            "bid" process, for purposes of play model training).  If not specified,
            the `bid_strat` instance will be used.

          - `base_play_stat` (object or config name) is used to play cards for the
            three other positions (not `play_pos`) during play traversal, including
            the `play_pos` partner.
        """
        super().__init__(**kwargs)
        if not self.bid_strat:
            raise ConfigError("'bid_strat' must be specified")
        if isinstance(self.bid_strat, str):
            self.bid_strat = Strategy.new(self.bid_strat)
        if not isinstance(self.bid_strat, Strategy):
            raise ConfigError("'bid_strat' must resolve to a Strategy subclass")

        if self.discard_strat:
            if isinstance(self.discard_strat, str):
                self.discard_strat = Strategy.new(self.discard_strat)
            if not isinstance(self.discard_strat, Strategy):
                raise ConfigError("'discard_strat' must resolve to a Strategy subclass")

        if not self.base_play_strat:
            raise ConfigError("'base_play_strat' must be specified")
        if isinstance(self.base_play_strat, str):
            self.base_play_strat = Strategy.new(self.base_play_strat)
        if not isinstance(self.base_play_strat, Strategy):
            raise ConfigError("'base_play_strat' must resolve to a Strategy subclass")

        self.play_analysis = self.play_analysis or {}
        if not self.hand_analysis:
            self.hand_analysis = self.play_analysis

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        return self.bid_strat.bid(deal, def_bid)

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        if not self.discard_strat:
            return self.bid_strat.discard(deal)
        return self.discard_strat.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        play_pos = os.environ.get('PLAY_DATA_POS')
        assert play_pos is not None
        if deal.pos != int(play_pos):
            return self.base_play_strat.play_card(deal, trick, valid_plays)

        if self.my_plays is None:
            bid_analysis = BidDataAnalysis(deal, **self.hand_analysis)
            self.bid_features = bid_analysis.get_features(deal.contract)
            # See PERF NOTE in `notify()` for bid_strategy.py.  Here, we make
            # queue a member variable, since this is the only position (hence
            # Strategy instantiation) that will be doing traversal.
            self.queue = mp.Queue()
            # Spawn subprocesses to handle the cards in `valid_plays` (other
            # than the first one, which we will handle ourselves)
            child_pids = []
            #for i in range(1, len(valid_plays)):
            for i in range(1, min(len(valid_plays), 1)):
                card = valid_plays[i]
                child_pid = os.fork()
                if child_pid == 0:
                    break
                status = os.waitpid(-1, 0)
                #child_pids.append(child_pid)
            else:
                card = valid_plays[0]
                self.main_proc = True
                assert self.child_pids is None
                self.child_pids = child_pids
            self.my_plays = [card]
        else:
            # now playing subsequent tricks, `self.main_proc` has already been
            # determined (and continues to own the listening end of the queue)
            assert isinstance(self.my_plays, list)
            assert len(self.my_plays) > 0
            assert isinstance(self.queue, Queue)
            # as above, we will handle the first element in `valid_plays`, and
            # spawn subprocesses if/as needed for the other plays
            child_pids = []
            #for i in range(1, len(valid_plays)):
            for i in range(1, min(len(valid_plays), 1)):
                card = valid_plays[i]
                child_pid = os.fork()
                if child_pid == 0:
                    break
                status = os.waitpid(-1, 0)
                #child_pids.append(child_pid)
            else:
                card = valid_plays[0]
                if self.child_pids is None:
                    assert not self.main_proc
                    self.child_pids = child_pids
                else:
                    self.child_pids.extend(child_pids)
            self.my_plays.append(card)

        analysis = PlayDataAnalysis(deal, **self.play_analysis,
                                    valid_plays=valid_plays,
                                    bid_features=self.bid_features)
        self.play_context = analysis.get_context(card)
        self.play_features = analysis.get_features(card)
        return card

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """Write feature set based on traversal on `DEAL_COMPLETE` notification,
        also ensure that child processes completed successfully
        """
        if not self.my_plays:
            return

        if self.child_pids:
            hdr = f"pid {os.getpid()} my_plays {' '.join(str(c) for c in self.my_plays)}:"
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

        self.play_outcome = PlayOutcome(deal.my_tricks_won, deal.my_points)
        my_features = list(self.play_features) + list(self.play_outcome)

        if DEBUG:
            self.play_context.cur_hand.cards.sort(key=lambda c: c.sortkey)
            log.debug(', '.join(f"{k}: {v}" for k, v in self.play_context._asdict().items()))
            log.debug(list(self.play_features) + list(self.play_outcome))

        def dequeue_print(file: TextIO = sys.stdout) -> None:
            try:
                while True:
                    features = self.queue.get_nowait()
                    features_str = '\t'.join(str(x) for x in features)
                    print(features_str, file=file)
            except queue.Empty:
                pass

        if self.main_proc:
            # HACK: see comments in bid_data.py!
            if data_file := os.environ.get('PLAY_DATA_FILE'):
                if not os.path.exists(data_file):
                    header = PlayFeatures._fields + PlayOutcome._fields
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
                header = PlayFeatures._fields + PlayOutcome._fields
                header_str = '\t'.join(header)
                my_features_str = '\t'.join(str(x) for x in my_features)
                print(header_str)
                print(my_features_str)
                dequeue_print()

            # need to reset the class, so this works for the next deal
            self.main_proc     = False
            self.queue         = None
            self.bid_features  = None
            self.play_context  = None
            self.play_features = None
            self.play_outcome  = None
            self.child_pids    = None
            self.my_plays      = None
        else:
            self.queue.put(my_features)
            self.queue.close()
            # if we spawned the process, we need to terminate it, so it doesn't continue
            # processing downstream outside of our purview
            sys.exit(0)
