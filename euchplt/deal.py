#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from typing import Optional

from .card import SUITS, Card, Hand, Deck, get_deck
from .euchre import Bid, NULL_BID, defend_suit
from .player import Player

########
# Deal #
########

class Deal(object):
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
    tricks:     list[Card]
    contract:   Optional[Bid]
    caller_pos: Optional[int]
    go_alone:   Optional[bool]
    def_alone:  Optional[bool]
    def_pos:    Optional[int]  # only used if `def_alone` is True
    
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

    @property
    def deal_state(self):
        return {}

    def is_passed(self) -> bool:
        """Typically called after `play_bids()` (not much sense in calling otherwise)
        """
        return len(self.bids) == len(self.players) * 2 and not self.contract

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
            self.hands.append(self.deck[i:deal_cards:num_players])
        self.turn_card = self.deck[deal_cards]
        self.buries = self.deck[deal_cards+1:]
        assert set([c for h in self.hands for c in h] + [self.turn_card] + self.buries) == \
            set(self.deck)

    def play_bids(self) -> None:
        """
        """
        num_players = len(self.players)
        dealer_pos  = num_players - 1
        # first round of bidding
        for pos in range(num_players):
            bid = self.players[pos].bid(self.deal_state)
            self.bids.append(bid)
            if bid.is_pass():
                continue
            # TODO: convert assert into proper exception logic!!!
            assert bid.suit == self.turn_card.suit
            self.contract   = bid
            self.caller_pos = pos
            self.go_alone   = bid.alone

            discard = self.players[dealer_pos].pick_up(self.deal_state)
            # TODO: convert assert into proper exception logic!!!
            assert discard in self.hands[dealer_pos]
            self.hands[dealer_pos].append(self.turn_card)
            self.hands[dealer_pos].remove(discard)
            self.buries.append(discard)
            # note that we don't erase `self.turn_card` even though it is actually now in the
            # bidder's hand--we keep it for posterity (kind of like `self.deck`)
            break

        if not self.contract:
            self.buries.append(self.turn_card)  # proverbial "turning it over"

            # second round of bidding
            for pos in range(num_players):
                bid = self.players[pos].bid(self.deal_state)
                self.bids.append(bid)
                if bid.is_pass():
                    continue
                # TODO: convert assert into proper exception logic!!!
                assert bid.suit in SUITS and bid.suit != self.turn_card.suit
                self.contract   = bid
                self.caller_pos = pos
                self.go_alone   = bid.alone
                break

        # check if deal is passed
        if not self.contract:
            return
        else:
            assert self.caller_pos

        # see if any opponents want to defend alone
        for i in range(1, num_players):
            pos = (self.caller_pos + i) % num_players
            # NOTE: we do something kind of stupid here to avoid making the partner `Player`
            # return a perfunctory "null" bid
            if i % 2 != 0:  # <-- this is what's stupid!
                # REVISIT: we are currently being nice and allowing the opponent `Player` to
                # return either "pass", "null", or "defend" bids, with or without the `alone`
                # flag set, but LATER we may make the protocol more rigid!!!
                bid = self.players[pos].bid(self.deal_state)
            else:
                bid = NULL_BID
            # we record this for traceability, even if not technically a real bid
            self.bids.append(bid)
            if bid.is_pass(include_null = True):
                continue
            # TODO: convert asserts into proper exception logic (see NOTE above for rules)!!!
            assert bid.suit == defend_suit
            self.def_alone = bid.alone
            self.def_pos   = pos
            if bid.alone:
                break
            # otherwise keep looping...
        # nothing left to do, so now return
        
    def play_cards(self) -> None:
        pass

########
# main #
########

def main() -> int:
    """Built-in driver to run through a simple/sample deal
    """
    players    = [Player() for i in range(4)]
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
