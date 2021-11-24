#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from typing import Optional

from .core import ImplementationError
from .card import SUITS, Card, Deck, get_deck
from .euchre import GameCtxMixin, Hand, Trick, Bid, PASS_BID, NULL_BID, DealState
from .player import Player

#############
# DealPhase #
#############

DealPhase = Enum('DealPhase', 'NEW BIDDING PASSED CONTRACT PLAYING COMPLETE SCORED')

########
# Deal #
########

class Deal(GameCtxMixin):
    """Represents the lifecycle of a deal, from the dealing of hands to bidding to
    playing tricks.  Note that `deck` is not shuffled in this class, it is up to the
    instantiator as to what it looks like; see `deal_cards()` for the implications.
    """
    players:    list[Player]   # ordered by position (0 = first bid, 3 = dealer)
    deck:       Deck
    hands:      list[Hand]     # same order as players, above
    turn_card:  Optional[Card]
    buries:     list[Card]
    bids:       list[Bid]
    tricks:     list[Trick]
    contract:   Optional[Bid]
    caller_pos: Optional[int]
    go_alone:   Optional[bool]
    def_alone:  Optional[bool]
    def_pos:    Optional[int]  # only used if `def_alone` is True
    tricks_won: list[int]      # by position, same for both partners
    points:     list[int]      # same as for `tricks_won`
    
    def __init__(self, players: list[Player], deck: Deck):
        """
        """
        self.players    = players
        self.deck       = deck
        self.hands      = []
        self.turn_card  = None
        self.buries     = []
        self.bids       = []
        self.tricks     = []
        self.contract   = None
        self.caller_pos = None
        self.go_alone   = None
        self.def_alone  = None
        self.def_pos    = None
        self.tricks_won = []
        self.points     = []

    def deal_state(self, pos: int) -> DealState:
        """
        """
        # REVISIT: this is a clunky way of narrowing the full state of the deal for the
        # specified position, but we can optimize LATER!!!
        return DealState(pos, self.hands[pos], self.turn_card, self.bids, self.tricks,
                         self.contract, self.caller_pos, self.go_alone, self.def_alone,
                         self.def_pos)

    @property
    def deal_phase(self) -> DealPhase:
        """
        """
        if not self.bids:
            assert not self.contract
            assert self.caller_pos is None
            return DealPhase.NEW
        elif not self.contract:
            assert self.caller_pos is None
            return DealPhase.BIDDING

        total_tricks = (len(self.deck) - len(self.buries)) // len(self.players)
        if not self.tricks:
            assert isinstance(self.caller_pos, int)
            return DealPhase.PASSED if self.is_passed() else DealPhase.CONTRACT
        elif len(self.tricks) < total_tricks:
            assert not self.points
            return DealPhase.PLAYING
        elif not self.points:
            assert len(self.tricks) == total_tricks
            return DealPhase.COMPLETE
        else:
            assert len(self.tricks) == total_tricks
            return DealPhase.SCORED

    def is_passed(self) -> bool:
        """Typically called after `play_bids()` (not much sense in calling otherwise)
        """
        return self.contract and self.contract == PASS_BID

    def valid_plays(self, pos: int) -> list[Card]:
        """
        """
        if not self.lead_card:
            # make a copy here just in case `self.hands` is modified before the return
            # list is fully utilized (note that the other case returns a standalone list
            # as well)
            return self.hands[pos].copy()
        return self.hands[pos].playable_cards(self)

    def set_score(self, pos: int, points: int) -> list[int]:
        """Set score for the specified position and its partner (0 for the opponents)
        """
        self.points = [0] * len(self.players)
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
                return self.set_score(self.caller_pos, 4)
            else:
                return self.set_score(self.caller_pos, 2)
        elif self.def_alone:
            return self.set_score(self.def_pos, 4)
        else:
            return self.set_score(self.def_pos, 2)

    def deal_cards(self) -> None:
        """Note that the hands, turn card, and buries derived from the deck depend on the
        dealing technique encoded here, which will be single-card round robin distribution
        for now.  LATER, we can play around with dealing in twos and threes, coupled with
        various gathering/shuffling schemes, to see the implications of real-world "card
        handling".
        """
        num_players = len(self.players)
        hand_cards  = 5
        deal_cards  = num_players * hand_cards
        
        for i in range(num_players):
            self.hands.append(Hand(self.deck[i:deal_cards:num_players]))
        self.turn_card = self.deck[deal_cards]
        self.buries = self.deck[deal_cards+1:]
        assert set([c for h in self.hands for c in h] + [self.turn_card] + self.buries) == \
            set(self.deck)

    def play_bids(self) -> Bid:
        """Returns contract bid, or PASS_BID if the deal is passed
        """
        assert self.deal_phase == DealPhase.NEW
        num_players = len(self.players)
        dealer_pos  = num_players - 1

        # first round of bidding
        for pos in range(num_players):
            bid = self.players[pos].bid(self.deal_state(pos))
            self.bids.append(bid)
            if bid.is_pass():
                continue
            if bid.suit != self.turn_card.suit:
                raise ImplementationError("Player: bad first round bid")
            self.contract   = bid
            self.caller_pos = pos
            self.go_alone   = bid.alone

            self.hands[dealer_pos].append(self.turn_card)
            discard = self.players[dealer_pos].discard(self.deal_state(pos))
            if discard not in self.hands[dealer_pos]:
                raise ImplementationError("Player: bad discard")
            self.hands[dealer_pos].remove(discard)
            self.buries.append(discard)
            # note that we don't erase `self.turn_card` even though it is actually now in the
            # bidder's hand--we keep it for posterity (kind of like `self.deck`)
            break

        if not self.contract:
            self.buries.append(self.turn_card)  # proverbial "turning it over"

            # second round of bidding
            for pos in range(num_players):
                bid = self.players[pos].bid(self.deal_state(pos))
                self.bids.append(bid)
                if bid.is_pass():
                    continue
                if bid.suit not in SUITS or bid.suit == self.turn_card.suit:
                    raise ImplementationError("Player: bad second round bid")
                self.contract   = bid
                self.caller_pos = pos
                self.go_alone   = bid.alone
                break

        # check if deal is passed
        if not self.contract:
            self.contract = PASS_BID
            return self.contract
        else:
            self.set_trump_suit(self.contract.suit)
            assert isinstance(self.caller_pos, int)

        if self.go_alone:
            # see if any opponents want to defend alone
            for i in range(1, num_players):
                pos = (self.caller_pos + i) % num_players
                # NOTE: we do something kind of stupid here to avoid making the partner `Player`
                # return a perfunctory "null" bid
                if i % 2 != 0:  # <-- this is what's stupid!
                    # REVISIT: we are currently being nice and allowing the opponent `Player` to
                    # return either "pass", "null", or "defend" bids, with or without the `alone`
                    # flag set, but LATER we may make the protocol more rigid!!!
                    bid = self.players[pos].bid(self.deal_state(pos))
                else:
                    bid = NULL_BID
                # we record this for traceability, even if not technically a real bid
                self.bids.append(bid)
                if bid.is_pass(include_null=True):
                    continue
                if not bid.is_defend():
                    raise ImplementationError("Player: bad defender bid")
                self.def_alone = bid.alone
                self.def_pos   = pos
                if bid.alone:
                    break
                # otherwise keep looping...

        return self.contract
        
    def play_cards(self) -> list[int]:
        """Return points resulting from this deal (list indexed by position)
        """
        assert self.deal_phase == DealPhase.CONTRACT
        total_tricks = (len(self.deck) - len(self.buries)) // len(self.players)
        num_players  = len(self.players)
        lead_pos     = 0

        self.tricks_won = [0] * num_players
        for trick_no in range(total_tricks):
            cur_trick    = Trick([None] * num_players)  # index by pos, so preallocate
            winning_card = None
            winning_pos  = None
            for i in range(num_players):
                pos = (lead_pos + i) % num_players
                if self.go_alone and pos + self.caller_pos == num_players:
                    continue
                if self.def_alone and pos + self.def_pos == num_players:
                    continue
                valid_cards = self.valid_plays(pos)
                card = self.players[pos].play_card(self.deal_state(pos), valid_cards)
                if card not in valid_cards:
                    raise ImplementationError("Player: bad card played")
                assert cur_trick[pos] is None
                cur_trick[pos] = card
                if winning_card is None:
                    self.set_lead_card(card)
                    winning_card = card
                    winning_pos  = pos
                elif card.beats(winning_card, self):
                    winning_card = card
                    winning_pos  = pos
            self.tricks.append(cur_trick)
            self.tricks_won[winning_pos] += 1
            self.tricks_won[winning_pos ^ 0x02] += 1  # TODO: encapsulate this magic!!!
            self.set_lead_card(None)
            lead_pos = winning_pos

        return self.compute_score()

########
# main #
########

from .player import PlayerRandom

def main() -> int:
    """Built-in driver to run through a simple/sample deal
    """
    players    = [PlayerRandom() for _ in range(4)]
    deck       = get_deck()
    deal       = Deal(players, deck)

    deal.deal_cards()
    deal.play_bids()
    if deal.is_passed():
        print("Deal was passed")
        return 0
    deal.play_cards()

    return 0

if __name__ == '__main__':
    sys.exit(main())
