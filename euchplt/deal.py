#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import IntEnum, StrEnum
from typing import TextIO

from .utils import parse_argv
from .core import DEBUG, LogicError, ImplementationError
from .card import Suit, SUITS, Card, Deck, set_seed, get_deck
from .euchre import GameCtxMixin, Hand, Trick, Bid, PASS_BID, NULL_BID
from .euchre import DealState
from .player import Player, PlayerNotice

########
# Deal #
########

HAND_CARDS  = 5
NUM_PLAYERS = 4
BIDDER_POS  = 0   # meaning, initial bidder
DEALER_POS  = -1

DealPhase = IntEnum('DealPhase', 'NEW DEALT BIDDING PASSED CONTRACT PLAYING COMPLETE SCORED')

class DealAttr(StrEnum):
    MAKE      = "Make"
    ALL_5     = "All_5"
    GO_ALONE  = "Go_Alone"
    EUCHRE    = "Euchre"
    DEF_ALONE = "Defend_Alone"

class Deal(GameCtxMixin):
    """Represents the lifecycle of a deal, from the dealing of hands to bidding to
    playing tricks.  Note that `deck` is not shuffled in this class, it is up to the
    instantiator as to what it looks like; see `deal_cards()` for the implications.
    """
    players:          list[Player]    # by position (0 = first bid, 3 = dealer)
    deck:             Deck
    hands:            list[Hand]      # by position (active)
    turn_card:        Card | None
    buries:           list[Card]
    bids:             list[Bid]
    def_bids:         list[Bid]
    discard:          Card | None
    tricks:           list[Trick]
    contract:         Bid | None
    caller_pos:       int | None
    go_alone:         bool | None
    def_alone:        bool | None     # only used if `go_alone`
    def_pos:          int | None      # only used if `def_alone`
    cards_dealt:      list[Hand]      # by position (for posterity)
    played_by_pos:    list[Hand]      # by order of play for a position
    played_by_suit:   dict[Suit, Hand]  # by order of play within a suit
    unplayed_by_suit: dict[Suit, set[Card]]  # using sets within a suit
    tricks_won:       list[int]       # by position, same for both partners
    result:           set[DealAttr]
    points:           list[int]       # same as for `tricks_won`
    player_state:     list[dict]

    def __init__(self, players: list[Player], deck: Deck):
        """
        """
        if len(players) != NUM_PLAYERS:
            raise LogicError(f"Expecting {NUM_PLAYERS} players, got {len(players)}")
        self.players          = players
        self.deck             = deck
        self.hands            = []
        self.turn_card        = None
        self.buries           = []
        self.bids             = []
        self.def_bids         = []
        self.discard          = None
        self.tricks           = []
        self.contract         = None
        self.caller_pos       = None
        self.go_alone         = None
        self.def_alone        = None
        self.def_pos          = None
        self.cards_dealt      = []
        self.played_by_pos    = []
        self.played_by_suit   = {}
        self.unplayed_by_suit = {}
        self.tricks_won       = []
        self.result           = set()
        self.points           = []
        self.player_state     = []
        for player in self.players:
            # shhh...
            self.player_state.append({'_deal': self} if player.priv() else {})

    def deal_state(self, pos: int) -> DealState:
        """REVISIT: this is a clunky way of narrowing the full state of the deal for the
        specified position, but we can optimize LATER!!!
        """
        # do fixup on `pos`, to account for DEALER_POS and possibly bidding rounds
        pos %= NUM_PLAYERS
        return DealState(pos, self.hands[pos], self.turn_card, self.bids, self.def_bids,
                         self.tricks, self.contract, self.caller_pos, self.go_alone,
                         self.def_alone, self.def_pos, self.played_by_suit,
                         self.unplayed_by_suit, self.tricks_won, self.points,
                         self.player_state[pos])

    @property
    def total_tricks(self) -> int:
        """Return total number of tricks for the deal
        """
        assert HAND_CARDS == (len(self.deck) - len(self.buries) - 1) // NUM_PLAYERS
        return HAND_CARDS

    @property
    def player_cards(self) -> int:
        """Number of cards to be dealt to players (i.e. excludes buries and turn card)
        """
        return NUM_PLAYERS * HAND_CARDS

    @property
    def deal_phase(self) -> DealPhase:
        """
        """
        if not self.cards_dealt:
            assert not self.bids
            return DealPhase.NEW

        if not self.bids:
            assert not self.contract
            assert self.caller_pos is None
            return DealPhase.DEALT

        if not self.contract:
            assert self.caller_pos is None
            return DealPhase.BIDDING

        if not self.tricks:
            if self.is_passed():
                return DealPhase.PASSED
            assert isinstance(self.caller_pos, int)
            return DealPhase.CONTRACT

        if len(self.tricks) < self.total_tricks:
            assert not self.points
            return DealPhase.PLAYING

        assert len(self.tricks) == self.total_tricks
        if not self.points:
            return DealPhase.COMPLETE
        return DealPhase.SCORED

    def is_passed(self) -> bool:
        """Typically called after `do_bidding()` (not much sense in calling otherwise)
        """
        return self.contract and self.contract == PASS_BID

    def prep_for_play(self) -> None:
        self.tricks_won     = [0] * NUM_PLAYERS
        self.played_by_pos  = [Hand([]) for _ in range(NUM_PLAYERS)]
        self.played_by_suit = {s: Hand([]) for s in SUITS}
        self.unplayed_by_suit = {s: set() for s in SUITS}
        for card in self.deck:
            self.unplayed_by_suit[card.effsuit(self)].add(card)

    def valid_plays(self, pos: int, trick: Trick) -> list[Card]:
        """
        """
        if not trick.lead_card:
            # make a copy here just in case `self.hands` is modified before the return
            # list is fully utilized (note that the other case returns a standalone list
            # as well)
            return self.hands[pos].copy_cards()
        return self.hands[pos].playable_cards(trick)

    def notify_players(self, notice: PlayerNotice) -> None:
        for pos, player in enumerate(self.players):
            player.notify(self.deal_state(pos), notice)

    def tabulate(self, trick: Trick) -> None:
        """
        """
        self.tricks_won[trick.winning_pos] += 1
        self.tricks_won[trick.winning_pos ^ 0x02] += 1  # TODO: fix magic!!!

    def set_score(self, pos: int, points: int) -> None:
        """Set score for the specified position and its partner (0 for the opponents)
        """
        self.points = [0] * NUM_PLAYERS
        self.points[pos] = points
        self.points[pos ^ 0x02] = points

    def compute_score(self) -> None:
        """In addition to computing the score, this also sets the DealAttr tags in
        `self.result`; calls set_score() to record the score
        """
        assert self.deal_phase == DealPhase.COMPLETE
        make   = self.tricks_won[self.caller_pos] >= 3
        all_5  = self.tricks_won[self.caller_pos] == 5

        if make:
            self.result.add(DealAttr.MAKE)
        else:
            self.result.add(DealAttr.EUCHRE)
        if all_5:
            self.result.add(DealAttr.ALL_5)
        if self.go_alone:
            self.result.add(DealAttr.GO_ALONE)
        if self.def_alone:
            self.result.add(DealAttr.DEF_ALONE)

        if DealAttr.MAKE in self.result:
            if DealAttr.ALL_5 in self.result:
                if DealAttr.GO_ALONE in self.result:
                    self.set_score(self.caller_pos, 4)
                else:
                    self.set_score(self.caller_pos, 2)
            else:
                self.set_score(self.caller_pos, 1)
        else:
            assert DealAttr.EUCHRE in self.result
            if DealAttr.DEF_ALONE in self.result:
                self.set_score(self.def_pos, 4)
            else:
                self.set_score(self.caller_pos ^ 0x01, 2)  # TODO: fix magic!!!
        # make sure all branches set the score
        assert self.points

    def deal_cards(self) -> None:
        """Note that the hands, turn card, and buries derived from the deck depend on the
        dealing technique encoded here, which will be single-card round robin distribution
        for now.  LATER, we can play around with dealing in twos and threes, coupled with
        various gathering/shuffling schemes, to see the implications of real-world "card
        handling".
        """
        for i in range(NUM_PLAYERS):
            hand = Hand(self.deck[i:self.player_cards:NUM_PLAYERS])
            self.cards_dealt.append(hand)
            self.hands.append(hand.copy())
        self.turn_card = self.deck[self.player_cards]
        self.buries = self.deck[self.player_cards+1:]
        in_play = [c for h in self.hands for c in h] + [self.turn_card] + self.buries
        assert set(in_play) == set(self.deck)
        self.notify_players(PlayerNotice.CARDS_DEALT)

    def do_bidding(self) -> Bid:
        """Returns contract bid, or PASS_BID if the deal is passed
        """
        assert self.deal_phase == DealPhase.DEALT

        # first round of bidding
        for pos in range(NUM_PLAYERS):
            bid = self.players[pos].bid(self.deal_state(pos))
            self.bids.append(bid)
            if bid.is_pass():
                continue
            if bid.suit != self.turn_card.suit:
                raise ImplementationError(f"Bad first round bid from {self.players[pos]}")
            self.contract   = bid
            self.caller_pos = pos
            self.go_alone   = bid.alone
            self.set_trump_suit(bid.suit)

            self.hands[DEALER_POS].append_card(self.turn_card, self)
            discard = self.players[DEALER_POS].discard(self.deal_state(DEALER_POS))
            if discard not in self.hands[DEALER_POS]:
                raise ImplementationError(f"Bad discard from {self.players[pos]}")
            self.hands[DEALER_POS].remove_card(discard, self)
            assert not self.discard
            self.discard = discard
            # note that we don't erase `self.turn_card` even though it is actually now in the
            # bidder's hand--we keep it for posterity (kind of like `self.deck`)
            break

        if not self.contract:
            # second round of bidding
            for pos in range(NUM_PLAYERS):
                bid = self.players[pos].bid(self.deal_state(pos))
                self.bids.append(bid)
                if bid.is_pass():
                    continue
                if bid.suit not in SUITS or bid.suit == self.turn_card.suit:
                    raise ImplementationError(f"Bad second round bid from {self.players[pos]}")
                self.contract   = bid
                self.caller_pos = pos
                self.go_alone   = bid.alone
                self.set_trump_suit(bid.suit)
                break

        # check if deal is passed
        if not self.contract:
            self.notify_players(PlayerNotice.BIDDING_OVER)
            self.notify_players(PlayerNotice.DEAL_COMPLETE)
            self.contract = PASS_BID
            return self.contract
        assert isinstance(self.caller_pos, int)

        if self.go_alone:
            # see if any opponents want to defend alone
            for i in range(1, NUM_PLAYERS):
                pos = (self.caller_pos + i) % NUM_PLAYERS
                # NOTE: we do something kind of stupid here to avoid making the partner `Player`
                # return a perfunctory "null" bid
                if i % 2 != 0:  # <-- this is what's stupid!
                    # REVISIT: we are currently being nice and allowing the opponent `Player` to
                    # return either "pass", "null", or "defend" bids, with or without the `alone`
                    # flag set, but LATER we may make the protocol more rigid!!!
                    bid = self.players[pos].bid(self.deal_state(pos), def_bid=True)
                else:
                    bid = NULL_BID
                # we record this for traceability, even if not technically a real bid
                self.bids.append(bid)
                self.def_bids.append(bid)
                if bid.is_pass(include_null=True):
                    continue
                if not bid.is_defend():
                    raise ImplementationError(f"Bad defender bid from {self.players[pos]}")
                if bid.alone:
                    self.def_alone = bid.alone
                    self.def_pos   = pos
                    break
                # otherwise keep looping...

        self.notify_players(PlayerNotice.BIDDING_OVER)
        return self.contract

    def play_cards(self) -> None:
        """Return points resulting from this deal (list indexed by position)
        """
        assert self.deal_phase == DealPhase.CONTRACT
        lead_pos = 0

        self.prep_for_play()
        for trick_num in range(self.total_tricks):
            trick = Trick(self)
            self.tricks.append(trick)
            for i in range(NUM_PLAYERS):
                pos = (lead_pos + i) % NUM_PLAYERS
                if self.go_alone and pos == self.caller_pos ^ 0x02:  # TODO: fix magic!!!
                    trick.play_card(pos, None)
                    continue
                if self.def_alone and pos == self.def_pos ^ 0x02:  # TODO: fix magic!!!
                    trick.play_card(pos, None)
                    continue
                valid_plays = self.valid_plays(pos, trick)
                card = self.players[pos].play_card(self.deal_state(pos), trick, valid_plays)
                if card not in valid_plays:
                    raise ImplementationError(f"Invalid play ({card}) from {self.players[pos]}")
                trick.play_card(pos, card)
                self.hands[pos].remove_card(card, self)
                self.played_by_pos[pos].append_card(card)
                self.played_by_suit[card.effsuit(self)].append_card(card)
                self.unplayed_by_suit[card.effsuit(self)].remove(card)
            self.tabulate(trick)
            lead_pos = trick.winning_pos
            self.notify_players(PlayerNotice.TRICK_COMPLETE)

        self.compute_score()
        self.notify_players(PlayerNotice.DEAL_COMPLETE)

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """Setting the `verbose` flag (or DEBUG mode) will print out details
        for individual tricks
        """
        if self.deal_phase < DealPhase.DEALT:
            return
        verbose = max(verbose, DEBUG)

        print("Hands:", file=file)
        for pos in range(NUM_PLAYERS):
            cards = self.cards_dealt[pos].copy_cards()
            cards.sort(key=lambda c: c.sortkey)
            print(f"  {self.players[pos].name}: {Hand(cards)}", file=file)

        print(f"Turn card:\n  {self.turn_card}", file=file)
        print(f"Buries:\n  {Hand(self.buries)}", file=file)

        if self.deal_phase < DealPhase.BIDDING:
            return

        print("Bids:", file=file)
        for pos, bid in enumerate(self.bids):
            alone = " alone" if bid.alone else ""
            print(f"  {self.players[pos % NUM_PLAYERS].name}: {bid.suit}{alone}", file=file)

        if self.deal_phase == DealPhase.PASSED:
            print("No bids, deal is passed", file=file)
            return

        if self.discard:
            print(f"Dealer Pickup:\n  {self.turn_card}", file=file)
            print(f"Dealer Discard:\n  {self.discard}", file=file)
            cards = self.played_by_pos[DEALER_POS].copy_cards()
            cards.sort(key=lambda c: c.sortkey)
            print(f"Dealer Hand (updated):\n  {self.players[DEALER_POS].name}: {Hand(cards)}",
                  file=file)

        if verbose:
            print("Tricks:", file=file)
            for trick_num, trick in enumerate(self.tricks):
                print(f"  Trick #{trick_num + 1}:", file=file)
                for play in trick.plays:
                    win = " (win)" if trick.winning_pos == play[0] else ""
                    print(f"    {self.players[play[0]].name}: {play[1]}{win}", file=file)

        self.print_score(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        """
        """
        if self.deal_phase < DealPhase.PLAYING:
            return

        print("Tricks Won:", file=file)
        for i in range(2):
            caller = " (caller)" if self.caller_pos % 2 == i else ""
            print(f"  {self.players[i].name}/{self.players[i+2].name}: "
                  f"{self.tricks_won[i]}{caller}", file=file)

        if self.deal_phase < DealPhase.SCORED:
            return

        print(f"Deal Result:  \n  {' '.join([res for res in self.result])}", file=file)
        print("Deal Points:", file=file)
        for i in range(2):
            caller = " (caller)" if self.caller_pos % 2 == i else ""
            print(f"  {self.players[i].name}/{self.players[i+2].name}: "
                  f"{self.points[i]}{caller}", file=file)

########
# main #
########

from .strategy import Strategy

DFLT_DEALS = 1
ITER_MULT = 100
DFLT_STRATEGY = 'Simple i'

def main() -> int:
    """Built-in driver to run through a simple/sample deal.

    Usage::

      python -m euchplt.deal [ndeals=<ndeals>] [result=<tags>] [strategy=<strategy>]
                             [rnd_seed=<seed>]

    If `result` is present, only deals with the indicated result tags(s) will be printed,
    specified as a comma-separated list of any number or combination of the following:
    `make`, `all_5`, `go_alone`, `euchre`, or `def_alone`.
    """
    # kwargs
    ndeals:      int = None  # deals to run (or print, if `result` is specified)
    result:      str = None  # comma-separated list of tags
    strategy:    str = None  # strategy name (or comma-separated list of two or four names)
    # local settings
    max_iters:   int = None
    result_tags: set[DealAttr] = None
    strategies:  list[Strategy] = None
    players:     list[Player] = None

    args, kwargs = parse_argv(sys.argv[1:])
    if len(args) > 0:
        args_str = ' '.join(str(arg) for arg in args)
        raise RuntimeError("Unexpected argument(s): " + args_str)
    ndeals = kwargs.pop('ndeals', DFLT_DEALS)
    if ndeals <= 0:
        raise RuntimeError("Bad value for `ndeals` specified")
    max_iters = ndeals * ITER_MULT  # set an upper bound on total iterations
    if result := kwargs.pop('result', None):
        attr_keys = result.upper().split(',')
        result_tags = set([DealAttr[x] for x in attr_keys])
    if strategy := kwargs.pop('strategy', None):
        strat_names = strategy.split(',')
        if len(strat_names) not in (1, 2, 4):
            raise RuntimeError("Only one, two, or four strategies can be specified")
        strategies = [Strategy.new(x) for x in strat_names]
    else:
        strategies = [Strategy.new(DFLT_STRATEGY)]
    if seed := kwargs.pop('rnd_seed', None):
        set_seed(seed)
    if kwargs:
        kwargs_str = ' '.join(str(kw) for kw in kwargs)
        raise RuntimeError("Unexpected argument(s): " + kwargs_str)

    nstrat = len(strategies)
    players = [Player(f"Player {i}", strategies[i % nstrat]) for i in range(4)]

    for _ in range(max_iters):
        deck = get_deck()
        deal = Deal(players, deck)

        deal.deal_cards()
        deal.do_bidding()
        if deal.is_passed():
            if not result_tags:
                deal.print()
            continue
        deal.play_cards()
        if not result_tags or result_tags <= deal.result:
            print("\n--- New Deal ---")
            deal.print(verbose=1)
            ndeals -= 1
            if ndeals <= 0:
                break

    return 0

if __name__ == '__main__':
    sys.exit(main())
