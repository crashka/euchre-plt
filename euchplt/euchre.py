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

class GameCtxMixin:
    """
    """
    _trump_suit: Suit
    _lead_card:  Card

    def set_trump_suit(self, trump_suit: Suit) -> None:
        """
        """
        self._trump_suit = trump_suit

    def set_lead_card(self, lead_card: Card) -> None:
        """
        """
        self._lead_card  = lead_card

    @property
    def trump_suit(self) -> Suit:
        try:
            return self._trump_suit
        except AttributeError:
            raise LogicError("`trump_suit` never set")

    @property
    def lead_card(self) -> Card:
        try:
            return self._lead_card
        except AttributeError:
            raise LogicError("`lead_card` never set")

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
        else:
            pass  # off-jack, fallthrough...
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
    """
    """
    ret = None
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

class Hand:
    """Behaves as list[Card] in iterable contexts
    """
    cards: list[Card]

    def __init__(self, cards: list[Card]):
        self.cards = cards

    def __getitem__(self, index):
        return self.cards[index]

    def __len__(self):
        return len(self.cards)

    def __getattr__(self, key):
        # Delegate to `self.cards`, primarily for the collection/iterator behavior
        try:
            return self.cards[key]
        except KeyError:
            raise AttributeError()

    def __repr__(self):
        return repr(self.cards)

    def __str__(self):
        return '  '.join(str(c) for c in self.cards)

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
        lead_suit = ctx.lead_card.effsuit(ctx)
        can_follow = bool(by_suit[lead_suit])
        if can_follow and card.effsuit(ctx) != lead_suit:
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

##############
# Play/Trick #
##############

Play = tuple[int, Card]  # [pos, card]

class Trick(GameCtxMixin):
    """
    """
    plays:        list[Play]            # sequential
    cards:        list[Optional[Card]]  # indexed by position
    winning_card: Optional[Card]
    winning_pos:  Optional[int]

    def __init__(self, parent_ctx: GameCtxMixin):
        self.plays        = []
        self.cards        = [None] * 4
        self.winning_card = None
        self.winning_pos  = None
        self.set_trump_suit(parent_ctx.trump_suit)

    def __repr__(self):
        return repr(self.plays)

    def __str__(self):
        return ' '.join(str(p[1]) for p in self.plays)

    def play_card(self, pos: int, card: Card) -> bool:
        """Returns `True` if new winning card
        """
        if self.cards[pos]:
            raise LogicError(f"Position {pos} played twice")
        self.cards[pos] = card
        self.plays.append((pos, card))
        if self.winning_card is None:
            self.set_lead_card(card)
            self.winning_card = card
            self.winning_pos  = pos
            return True
        if card.beats(self.winning_card, self):
            self.winning_card = card
            self.winning_pos  = pos
            return True
        return False

#######
# Bid #
#######

# NOT PRETTY: is there a nicer way to do this???
pass_suit   = Suit(-1, 'pass', 'pass')
null_suit   = Suit(-2, 'null', 'null')
defend_suit = Suit(-3, 'defend', 'defend')

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

    @property
    def cur_trick(self) -> Trick:
        return self.tricks[-1]

    @property
    def bid_round(self) -> int:
        return 1 if len(self.bids) < 4 else 2
