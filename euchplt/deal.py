#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from typing import Optional, TextIO

from .core import LogicError, ImplementationError
from .card import SUITS, Card, Deck, get_deck
from .euchre import GameCtxMixin, Hand, Trick, Bid, PASS_BID, NULL_BID, DealState
from .player import Player

########################
# DealPhase/DealResult #
########################

DealPhase = Enum('DealPhase', 'NEW DEALT BIDDING PASSED CONTRACT PLAYING COMPLETE SCORED')

class DealResult(Enum):
    MAKE         = "Make"
    MAKE_ALONE   = "Make alone"
    ALL_5        = "Make all 5"
    ALL_5_ALONE  = "Make all 5 alone"
    EUCHRE       = "Euchre"
    EUCHRE_ALONE = "Euchre alone"

########
# Deal #
########

HAND_CARDS  = 5
NUM_PLAYERS = 4
BIDDER_POS  = 0   # meaning, initial bidder
DEALER_POS  = -1

class Deal(GameCtxMixin):
    """Represents the lifecycle of a deal, from the dealing of hands to bidding to
    playing tricks.  Note that `deck` is not shuffled in this class, it is up to the
    instantiator as to what it looks like; see `deal_cards()` for the implications.
    """
    players:      list[Player]    # by position (0 = first bid, 3 = dealer)
    deck:         Deck
    hands:        list[Hand]      # by position
    turn_card:    Optional[Card]
    buries:       list[Card]
    bids:         list[Bid]
    discard:      Optional[Card]
    tricks:       list[Trick]
    contract:     Optional[Bid]
    caller_pos:   Optional[int]
    go_alone:     Optional[bool]
    def_alone:    Optional[bool]
    def_pos:      Optional[int]   # only used if `def_alone` is True
    cards_dealt:  list[Hand]      # by position
    cards_played: list[Hand]      # by position
    tricks_won:   list[int]       # by position, same for both partners
    points:       list[int]       # same as for `tricks_won`
    result:       Optional[DealResult]

    def __init__(self, players: list[Player], deck: Deck):
        """
        """
        if len(players) != NUM_PLAYERS:
            raise LogicError(f"Expecting {NUM_PLAYERS} players, got {len(players)}")
        self.players      = players
        self.deck         = deck
        self.hands        = []
        self.turn_card    = None
        self.buries       = []
        self.bids         = []
        self.discard      = None
        self.tricks       = []
        self.contract     = None
        self.caller_pos   = None
        self.go_alone     = None
        self.def_alone    = None
        self.def_pos      = None
        self.cards_dealt  = []
        self.cards_played = [Hand([]) for _ in range(NUM_PLAYERS)]
        self.tricks_won   = []
        self.points       = []
        self.result       = None

    def deal_state(self, pos: int) -> DealState:
        """REVISIT: this is a clunky way of narrowing the full state of the deal for the
        specified position, but we can optimize LATER!!!
        """
        # do fixup on `pos`, to account for DEALER_POS and possibly bidding rounds
        pos %= NUM_PLAYERS
        return DealState(pos, self.hands[pos], self.turn_card, self.bids, self.tricks,
                         self.contract, self.caller_pos, self.go_alone, self.def_alone,
                         self.def_pos)

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

        total_tricks = (len(self.deck) - len(self.buries)) // NUM_PLAYERS
        if len(self.tricks) < total_tricks:
            assert not self.points
            return DealPhase.PLAYING

        assert len(self.tricks) == total_tricks
        if not self.points:
            return DealPhase.COMPLETE
        return DealPhase.SCORED

    def is_passed(self) -> bool:
        """Typically called after `do_bidding()` (not much sense in calling otherwise)
        """
        return self.contract and self.contract == PASS_BID

    def valid_plays(self, pos: int, trick: Trick) -> list[Card]:
        """
        """
        if not trick.plays:
            # make a copy here just in case `self.hands` is modified before the return
            # list is fully utilized (note that the other case returns a standalone list
            # as well)
            return self.hands[pos].copy_cards()
        return self.hands[pos].playable_cards(trick)

    def set_score(self, pos: int, points: int) -> list[int]:
        """Set score for the specified position and its partner (0 for the opponents)
        """
        self.points = [0] * NUM_PLAYERS
        self.points[pos] = points
        self.points[pos ^ 0x02] = points
        return self.points

    def compute_score(self) -> list[int]:
        """
        """
        assert self.deal_phase == DealPhase.COMPLETE
        win    = self.tricks_won[self.caller_pos] >= 3
        all_5  = self.tricks_won[self.caller_pos] == 5
        if win:
            if self.go_alone and all_5:
                self.result = DealResult.ALL_5_ALONE
                return self.set_score(self.caller_pos, 4)
            elif all_5:
                self.result = DealResult.ALL_5
                return self.set_score(self.caller_pos, 2)
            else:
                self.result = DealResult.MAKE
                return self.set_score(self.caller_pos, 1)
        elif self.def_alone:
            self.result = DealResult.EUCHRE_ALONE
            return self.set_score(self.def_pos, 4)
        else:
            self.result = DealResult.EUCHRE
            return self.set_score(self.caller_pos ^ 0x01, 2)  # TODO: fix magic!!!

    def deal_cards(self) -> None:
        """Note that the hands, turn card, and buries derived from the deck depend on the
        dealing technique encoded here, which will be single-card round robin distribution
        for now.  LATER, we can play around with dealing in twos and threes, coupled with
        various gathering/shuffling schemes, to see the implications of real-world "card
        handling".
        """
        deal_cards = NUM_PLAYERS * HAND_CARDS

        for i in range(NUM_PLAYERS):
            hand = Hand(self.deck[i:deal_cards:NUM_PLAYERS])
            self.cards_dealt.append(hand)
            self.hands.append(hand.copy())
        self.turn_card = self.deck[deal_cards]
        self.buries = self.deck[deal_cards+1:]
        assert set([c for h in self.hands for c in h] + [self.turn_card] + self.buries) == \
            set(self.deck)

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

            self.hands[DEALER_POS].append_card(self.turn_card)
            discard = self.players[DEALER_POS].discard(self.deal_state(DEALER_POS))
            if discard not in self.hands[DEALER_POS]:
                raise ImplementationError(f"Bad discard from {self.players[pos]}")
            self.hands[DEALER_POS].remove_card(discard)
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
                break

        # check if deal is passed
        if not self.contract:
            self.contract = PASS_BID
            return self.contract
        self.set_trump_suit(self.contract.suit)
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
                if bid.is_pass(include_null=True):
                    continue
                if not bid.is_defend():
                    raise ImplementationError(f"Bad defender bid from {self.players[pos]}")
                if bid.alone:
                    self.def_alone = bid.alone
                    self.def_pos   = pos
                    break
                # otherwise keep looping...

        return self.contract

    def play_cards(self) -> list[int]:
        """Return points resulting from this deal (list indexed by position)
        """
        assert self.deal_phase == DealPhase.CONTRACT
        total_tricks = (len(self.deck) - len(self.buries)) // NUM_PLAYERS
        lead_pos     = 0

        self.tricks_won = [0] * NUM_PLAYERS
        for _ in range(total_tricks):
            trick = Trick(self)
            self.tricks.append(trick)
            for i in range(NUM_PLAYERS):
                pos = (lead_pos + i) % NUM_PLAYERS
                if self.go_alone and pos == self.caller_pos ^ 0x02:  # TODO: fix magic!!!
                    continue
                if self.def_alone and pos == self.def_pos ^ 0x02:  # TODO: fix magic!!!
                    continue
                valid_cards = self.valid_plays(pos, trick)
                card = self.players[pos].play_card(self.deal_state(pos), trick, valid_cards)
                if card not in valid_cards:
                    raise ImplementationError(f"Bad card played from {self.players[pos]}")
                trick.play_card(pos, card)
                self.hands[pos].remove_card(card)
                self.cards_played[pos].append_card(card)
            self.tricks_won[trick.winning_pos] += 1
            self.tricks_won[trick.winning_pos ^ 0x02] += 1  # TODO: fix magic!!!
            lead_pos = trick.winning_pos

        return self.compute_score()

    def print(self, file: TextIO = sys.stdout) -> None:
        """
        """
        names = [self.players[pos].name for pos in range(NUM_PLAYERS)]

        if self.deal_phase.value < DealPhase.DEALT.value:
            return

        print("Hands:", file=file)
        for pos in range(NUM_PLAYERS):
            cards = self.cards_dealt[pos].copy_cards()
            cards.sort(key=lambda c: c.sortkey)
            print(f"  {names[pos]}: {Hand(cards)}", file=file)

        print(f"Turn card:\n  {self.turn_card}", file=file)
        print(f"Buries:\n  {Hand(self.buries)}", file=file)

        if self.deal_phase.value < DealPhase.BIDDING.value:
            return

        print("Bids:", file=file)
        for pos, bid in enumerate(self.bids):
            alone = " alone" if bid.alone else ""
            print(f"  {names[pos % NUM_PLAYERS]}: {bid.suit}{alone}", file=file)

        if self.deal_phase == DealPhase.PASSED:
            print("No bids, deal is passed", file=file)
            return

        if self.discard:
            print(f"Dealer Pickup:\n  {self.turn_card}", file=file)
            print(f"Dealer Discard:\n  {self.discard}", file=file)
            cards = self.cards_played[DEALER_POS].copy_cards()
            cards.sort(key=lambda c: c.sortkey)
            print(f"Dealer Hand (updated):\n  {names[DEALER_POS]}: {Hand(cards)}", file=file)

        if self.deal_phase.value < DealPhase.PLAYING.value:
            return

        print("Tricks:", file=file)
        for trick_num, trick in enumerate(self.tricks):
            print(f"  Trick #{trick_num + 1}:", file=file)
            for play in trick.plays:
                win = " (win)" if trick.winning_pos == play[0] else ""
                print(f"    {names[play[0]]}: {play[1]}{win}", file=file)

        self.print_score(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        """
        """
        names = [self.players[pos].name for pos in range(NUM_PLAYERS)]

        if self.deal_phase.value < DealPhase.PLAYING.value:
            return

        print("Tricks Won:", file=file)
        for i in range(2):
            caller = " (caller)" if self.caller_pos % 2 == i else ""
            print(f"  {names[i]} / {names[i+2]}: {self.tricks_won[i]}{caller}", file=file)

        if self.deal_phase.value < DealPhase.SCORED.value:
            return

        print(f"Deal Result:  \n  {self.result.value}", file=file)
        print("Deal Points:", file=file)
        for i in range(2):
            caller = " (caller)" if self.caller_pos % 2 == i else ""
            print(f"  {names[i]} / {names[i+2]}: {self.points[i]}{caller}", file=file)

########
# main #
########

from .strategy import StrategyRandom, StrategySimple

def main() -> int:
    """Built-in driver to run through a simple/sample deal
    """
    players = [Player("Player 0", StrategyRandom),
               Player("Player 1", StrategySimple),
               Player("Player 2", StrategyRandom),
               Player("Player 3", StrategySimple)]

    deck = get_deck()
    deal = Deal(players, deck)

    deal.deal_cards()
    deal.do_bidding()
    if deal.is_passed():
        deal.print()
        return 0
    deal.play_cards()
    deal.print()

    return 0

if __name__ == '__main__':
    sys.exit(main())
