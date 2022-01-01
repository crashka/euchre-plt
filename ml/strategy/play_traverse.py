# -*- coding: utf-8 -*-

import os
import sys
from typing import ClassVar, Optional, NamedTuple
from dataclasses import dataclass
from multiprocessing.synchronize import Lock
import multiprocessing as mp
from numbers import Number
from time import sleep
import json

from euchplt.core import log, DEBUG, ConfigError, LogicError
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
    run_id:           str
    key:              str
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
    """Serves double-duty as the structure for capturing individual play
    outcomes (in which case min, max, and avg are all the same), as well
    as finally writing out the aggregated outcome features (output from
    `CompOutput.finalize()`)
    """
    tricks_min:       int
    tricks_max:       int
    tricks_avg:       float
    points_min:       int
    points_max:       int
    points_avg:       float

@dataclass
class CompOutcome:
    """Compute outcome by aggregating PlayOutcome and CompOutcome records
    """
    final:      bool  = False
    count:      int   = 0
    tricks_sum: int   = 0
    tricks_min: int   = 99999
    tricks_max: int   = -1
    tricks_avg: float = 0.0
    points_sum: int   = 0
    points_min: int   = 99999
    points_max: int   = -1
    points_avg: float = 0.0

    def empty(self) -> bool:
        return self.count == 0

    def add(self, outcome: PlayOutcome) -> None:
        if self.final:
            raise LogicError("Cannot add to finalized outcome")
        self.count += 1
        self.tricks_sum += outcome.tricks_avg
        self.tricks_min = min(self.tricks_min, outcome.tricks_min)
        self.tricks_max = max(self.tricks_max, outcome.tricks_max)
        self.points_sum += outcome.points_avg
        self.points_min = min(self.points_min, outcome.points_min)
        self.points_max = max(self.points_max, outcome.points_max)

    def combine(self, other: 'CompOutcome') -> None:
        if self.final:
            raise LogicError("Cannot combine to finalized outcome")
        self.count += other.count
        self.tricks_sum += other.tricks_avg
        self.tricks_min = min(self.tricks_min, other.tricks_min)
        self.tricks_max = max(self.tricks_max, other.tricks_max)
        self.points_sum += other.points_avg
        self.points_min = min(self.points_min, other.points_min)
        self.points_max = max(self.points_max, other.points_max)

    def finalize(self) -> PlayOutcome:
        self.tricks_avg = self.tricks_sum / self.count
        self.points_avg = self.points_sum / self.count
        self.final = True
        return PlayOutcome(self.tricks_min,
                           self.tricks_max,
                           self.tricks_avg,
                           self.points_min,
                           self.points_max,
                           self.points_avg)

###############
# PlayDataMsg #
###############

TraverseKey = tuple[Card, ...]

class PlayDataMsg(NamedTuple):
    pid:              int
    key:              TraverseKey
    context:          PlayContext
    features:         PlayFeatures
    outcome:          CompOutcome

####################
# PlayDataAnalysis #
####################

class PlayDataAnalysis(PlayAnalysis):
    """Manage features for generating data for "play" ML models
    """
    trump_values: list[int]
    run_id:       str
    valid_plays:  list[Card]
    bid_features: BidFeatures

    def __init__(self, deal: DealState, **kwargs):
        super().__init__(deal)
        self.trump_values = kwargs.get('trump_values')
        self.run_id       = kwargs.get('run_id')
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

    def get_features(self, card: Card, key: TraverseKey) -> PlayFeatures:
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
            'run_id'          : self.run_id,
            'key'             : ' '.join(str(c) for c in key),
            'trick_num'       : deal.trick_num,
            'play_seq'        : deal.play_seq,
            'pos'             : deal.pos,
            'partner_winning' : int(deal.partner_winning),
            'lead_trumped'    : int(not leading and deal.lead_trumped),
            'tricks_won'      : deal.my_tricks_won,
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

FMT_JSON    = 'json'
FMT_TSV     = 'tsv'
FMT_DFLT    = FMT_TSV

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

    run_id:          str           = None
    data_fmt:        str           = None
    main_proc:       bool          = False
    child_pids:      list[int]     = None
    my_plays:        list[Card]    = None
    bid_features:    BidFeatures   = None
    context:         PlayContext   = None
    features:        PlayFeatures  = None
    lock:            Lock          = None

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

    def write_header(self) -> None:
        """Not pretty to require its own `open()` call, but this is neater
        code-wise.  The header is not written if appending to an already
        existing data file.
        """
        header = PlayFeatures._fields + PlayOutcome._fields
        if self.data_fmt == FMT_JSON:
            header_str = json.dumps(header)
        else:
            assert self.data_fmt == FMT_TSV
            header_str = '\t'.join(header)
        if data_file := os.environ.get('PLAY_DATA_FILE'):
            if os.path.exists(data_file) and os.path.getsize(data_file) > 0:
                return
            with self.lock, open(data_file, 'a') as f:
                print(header_str, file=f)
        else:
            with self.lock:
                print(header_str)

    def write_features(self, features: PlayFeatures, outcome: PlayOutcome = None) -> None:
        """We append tab-delimited records to the specified data file; it is the
        responsibility of the main program to aggregate the results and compute
        outcomes for `play_seq` 1 through 4
        """
        outcome = outcome or []
        if self.data_fmt == FMT_JSON:
            msg = {'features': features, 'outcome': outcome}
            features_str = json.dumps(msg)
        else:
            assert self.data_fmt == FMT_TSV
            features_str = '\t'.join(str(x) for x in list(features) + list(outcome))
        if data_file := os.environ.get('PLAY_DATA_FILE'):
            with self.lock, open(data_file, 'a') as f:
                print(features_str, file=f)
        else:
            with self.lock:
                print(features_str)

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
        play_pos = os.environ.get('PLAY_DATA_POS')  # could put this in a class variable!
        assert play_pos is not None
        if deal.pos != int(play_pos):
            return self.base_play_strat.play_card(deal, trick, valid_plays)

        if self.my_plays is None:
            assert self.run_id is None
            self.run_id = os.environ.get('PLAY_DATA_RUN_ID')
            self.data_fmt = os.environ.get('PLAY_DATA_FORMAT', FMT_DFLT)
            bid_analysis = BidDataAnalysis(deal, **self.hand_analysis)
            self.bid_features = bid_analysis.get_features(deal.contract)
            # lock is used to synchronize I/O accross processes
            self.lock = mp.Lock()
            self.write_header()
            # Spawn subprocesses to handle the cards in `valid_plays` (other
            # than the first one, which we will handle ourselves)
            child_pids = []
            for i in range(1, len(valid_plays)):
                card = valid_plays[i]
                child_pid = os.fork()
                if child_pid == 0:
                    break
                child_pids.append(child_pid)
            else:
                card = valid_plays[0]
                self.main_proc = True
                assert self.child_pids is None
                self.child_pids = child_pids
            self.my_plays = [card]
        else:
            # now playing subsequent tricks, `self.main_proc` has already been
            # determined
            assert isinstance(self.my_plays, list)
            assert len(self.my_plays) > 0
            # as above, we will handle the first element in `valid_plays`, and
            # spawn subprocesses if/as needed for the other plays
            child_pids = []
            for i in range(1, len(valid_plays)):
                card = valid_plays[i]
                child_pid = os.fork()
                if child_pid == 0:
                    self.main_proc  = False
                    self.child_pids = None
                    break
                child_pids.append(child_pid)
            else:
                card = valid_plays[0]
                if self.child_pids is None:
                    assert not self.main_proc
                    self.child_pids = child_pids
                else:
                    self.child_pids.extend(child_pids)
            self.my_plays.append(card)

        analysis = PlayDataAnalysis(deal, **self.play_analysis,
                                    run_id=self.run_id,
                                    valid_plays=valid_plays,
                                    bid_features=self.bid_features)
        # for trick_num 5, features are written in `notify()` along with the
        # outcome information
        if deal.trick_num < 5:
            key = tuple(self.my_plays)
            context = analysis.get_context(card)
            features = analysis.get_features(card, key)
            self.write_features(features)
        else:
            key = tuple(self.my_plays)
            self.context = analysis.get_context(card)
            self.features = analysis.get_features(card, key)
        return card

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """Write feature set based on traversal on `DEAL_COMPLETE` notification,
        also ensure that child processes completed successfully
        """
        if not self.my_plays:
            return
        assert len(self.my_plays) == 5

        tricks_won = [deal.my_tricks_won] * 3
        points     = [deal.my_points] * 3
        outcome    = PlayOutcome(*tricks_won, *points)
        self.write_features(self.features, outcome)

        if self.child_pids:
            child_errs = []
            try:
                log.debug(f"waiting on child pids: {self.child_pids}")
                while len(self.child_pids) > 0:
                    status = os.waitpid(-1, 0)
                    log.debug(f"reaped child pid {status[0]} status {status[1]}")
                    self.child_pids.remove(status[0])
                    if status[1] != 0:
                        child_errs.append(status)
            except ChildProcessError as e:
                log.debug(f"caught ChildProcessError: {e}")
            if child_errs:
                hdr = f"pid {os.getpid()} ({' '.join(str(c) for c in self.my_plays)}):"
                raise RuntimeError(f"{hdr} error(s) in child processes: {child_errs}")

        if self.main_proc:
            # need to reset the class, so this works for the next deal
            self.main_proc    = False
            self.bid_features = None
            self.context      = None
            self.features     = None
            self.child_pids   = None
            self.my_plays     = None
            self.run_id       = None
            self.data_fmt     = None
        else:
            # if we spawned the process, we need to terminate it, so it doesn't
            # continue processing downstream outside of our purview
            os._exit(0)
