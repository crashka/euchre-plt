# -*- coding: utf-8 -*-
"""This module contains game-/domain-specific stuff on top of the (more) generic building
blocks (e.g. cards), and can be imported by either the player or game-playing modules
"""

from typing import Optional, NamedTuple

from .core import LogicError
from .card import SUITS, Suit, Card, jack, right, left

################
# GameCtxMixin #
################

class GameCtxMixin(object):
    """
    """
    _trump_suit: Suit
    _lead_card:  Optional[Card]

    def set_trump_suit(self, trump_suit: Suit) -> None:
        """
        """
        self._trump_suit = trump_suit

    def set_lead_card(self, lead_card: Optional[Card]) -> None:
        """Note that `lead_card` can be (re)set to `None`, since the context may be used
        for multiple tricks, and we want to maintain integrity between them (not inherit
        any stale state)
        """
        self._lead_card  = lead_card

    @property
    def trump_suit(self) -> Suit:
        try:
            return self._trump_suit
        except AttributeError:
            raise LogicError("'set_context' never called")

    @property
    def lead_card(self) -> Card:
        try:
            return self._lead_card
        except AttributeError:
            raise LogicError("'set_context' never called")

################
# augment Suit #
################

def opp_suit(self) -> Suit:
    """
    """
    opp_idx = self.idx ^ 0x3
    return SUITS[opp_idx]

setattr(Suit, 'opp_suit', opp_suit)

################
# augment Card #
################

def efflevel(self, ctx: GameCtxMixin) -> int:
    """
    """
    if ctx.trump_suit is None:
        raise LogicError("Trump suit not set")
    is_jack  = self.rank == jack
    is_trump = self.suit == ctx.trump_suit
    is_opp   = self.suit == ctx.trump_suit.opp_suit()
    if is_jack:
        if is_trump:
            return right.level
        elif is_opp:
            return left.level
    return self.level

def effsuit(self, ctx: GameCtxMixin) -> Suit:
    """
    """
    if ctx.trump_suit is None:
        raise LogicError("Trump suit not set")
    is_jack = self.rank == jack
    is_opp  = self.suit == ctx.trump_suit.opp_suit()
    if is_jack and is_opp:
        return ctx.trump_suit
    return self.suit

def beats(self, other: Card, ctx: GameCtxMixin) -> bool:
    """Added to `Card` from euchre.py due to circular dependency
    """
    # REVISIT: this is not very efficient or pretty, can probably do better by handling bower
    # suit and rank externally (e.g. replacing `Card`s in `Hand`s, once trump is declared)!!!
    self_trump  = self.effsuit(ctx) == ctx.trump_suit
    other_trump = other.effsuit(ctx) == ctx.trump_suit
    same_suit   = self.effsuit(ctx) == other.effsuit(ctx)
    if self_trump:
        ret = self.efflevel(ctx) > other.efflevel(ctx) if other_trump else True
    elif other_trump:
        ret = False
    else:
        ret = self.efflevel(ctx) > other.efflevel(ctx) if same_suit else True
    return ret

setattr(Card, 'efflevel', efflevel)
setattr(Card, 'effsuit', effsuit)
setattr(Card, 'beats', beats)

########
# Hand #
########

class Hand(object):
    """Behaves the same as list[Card]
    """
    cards:   list[Card]

    def __init__(self, cards: list[Card]):
        self.cards = cards

    def __getitem__(self, index):
        """
        """
        return self.cards[index]

    def __getattr__(self, key):
        """Delegate to `self.cards`, primarily for the collection/iterator behavior
        """
        try:
            return self.cards[key]
        except KeyError:
            raise AttributeError()

    def cards_by_suit(self, ctx: GameCtxMixin) -> dict[Suit, list[Card]]:
        """
        """
        by_suit = {suit: [] for suit in SUITS}
        for card in self.cards:
            by_suit[card.effsuit(ctx)].append(card)
        return by_suit

    def can_play(self, card: Card, ctx: GameCtxMixin) -> bool:
        """
        """
        if ctx.trump_suit is None:
            raise LogicError("Trump suit not set")
        if ctx.lead_card is None:
            raise LogicError("Lead card not set")
        by_suit = self.cards_by_suit(ctx)
        lead_suit = ctx.lead_card.suit
        can_follow = bool(by_suit[lead_suit])
        if can_follow and card.suit != lead_suit:
            return False
        return True

    def playable_cards(self, ctx: GameCtxMixin) -> list[Card]:
        """
        """
        playables = []
        for card in self.cards:
            if self.can_play(card, ctx):
                playables.append(card)
        return playables

#########
# Trick #
#########

class Trick(object):
    """Behaves the same as list[Card] (similar to `Hand`)
    """
    cards: list[Optional[Card]]

    def __init__(self, cards: list[Optional[Card]]):
        self.cards = cards

    def __getattr__(self, key):
        """Delegate to `self.cards`, primarily for the collection/iterator behavior
        """
        try:
            return self.cards[key]
        except KeyError:
            raise AttributeError()

#######
# Bid #
#######

# NOT PRETTY: is there a nicer way to do this???
pass_suit   = Suit(-1, 'pass', 'p')
null_suit   = Suit(-2, 'null', 'n')
defend_suit = Suit(-3, 'defend', 'd')

class Bid(NamedTuple):
    suit:  Suit          # either real suit or dummy suit
    alone: bool = False  # used for either bidding or defending

    def is_pass(self, include_null: bool = False) -> bool:
        if include_null and self.suit == null_suit:
            return True
        return self.suit == pass_suit

    def is_defend(self) -> bool:
        return self.suit == defend_suit

# convenience singletons
PASS_BID     = Bid(pass_suit)
NULL_BID     = Bid(null_suit)
DEFEND_ALONE = Bid(defend_suit, True)

#############
# DealState #
#############

class DealState(NamedTuple):
    pos:        int
    hand:       Hand
    turn_card:  Optional[Card]
    bids:       list[Bid]
    tricks:     list[Trick]
    contract:   Optional[Bid]
    caller_pos: Optional[int]
    go_alone:   Optional[bool]
    def_alone:  Optional[bool]
    def_pos:    Optional[int]
