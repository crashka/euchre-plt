# -*- coding: utf-8 -*-
"""This module contains game-/domain-specific stuff on top of the (more) generic building
blocks (e.g. cards), and can be imported by either the player or game-playing modules
"""

from typing import Optional, NamedTuple

from .core import LogicError
from .card import ALL_RANKS, SUITS, Suit, Card, jack, right, left, find_bower

################
# GameCtxMixin #
################

class GameCtxMixin:
    """We use private instance variables here to make the setter methods
    more explicit and differentiated from subclass variables
    """
    _trump_suit: Suit = None
    _lead_card:  Card = None

    def set_trump_suit(self, trump_suit: Suit) -> None:
        if self._trump_suit:
            raise LogicError(f"Cannot change trump_suit for {type(self).__name__}")
        self._trump_suit = trump_suit

    def set_lead_card(self, lead_card: Card) -> None:
        if self._lead_card:
            raise LogicError(f"Cannot change lead_card for {type(self).__name__}")
        self._lead_card = lead_card

    @property
    def trump_suit(self) -> Suit:
        return self._trump_suit

    @property
    def lead_card(self) -> Card:
        return self._lead_card

################
# augment Suit #
################

def next_suit(self) -> Suit:
    """Next relative to current suit (i.e. assuming it is trump)
    """
    return SUITS[self.idx ^ 0x3]

def green_suits(self) -> tuple[Suit, Suit]:
    """Green relative to current suit (i.e. assuming it is trump)
    """
    return SUITS[self.idx ^ 0x1], SUITS[self.idx ^ 0x2]

setattr(Suit, 'next_suit', next_suit)
setattr(Suit, 'green_suits', next_suit)

################
# augment Card #
################

def efflevel(self, ctx: GameCtxMixin, offset_trump: bool = False) -> int:
    """Note that this also works if jacks have been replaced with `Bower` types
    (e.g. by `Hand.cards_by_suit`)
    """
    level = None
    if ctx.trump_suit is None:
        raise LogicError("Trump suit not set")
    is_jack  = self.rank == jack
    is_trump = self.suit == ctx.trump_suit
    is_next  = self.suit == ctx.trump_suit.next_suit()
    if is_jack:
        if is_trump:
            level = right.level
        elif is_next:
            level = left.level
            is_trump = True
        else:
            level = self.level
    else:
        level = self.level
    assert isinstance(level, int)
    if is_trump and offset_trump:
        return level + len(ALL_RANKS)
    return level

def effsuit(self, ctx: GameCtxMixin) -> Suit:
    """
    """
    if ctx.trump_suit is None:
        raise LogicError("Trump suit not set")
    is_jack = self.rank == jack
    is_next = self.suit == ctx.trump_suit.next_suit()
    if is_jack and is_next:
        return ctx.trump_suit
    return self.suit

def effcard(self, ctx: GameCtxMixin) -> Card:
    """Translates trump and next suit jacks to bowers, otherwise returns self
    """
    bower = None
    if ctx.trump_suit is None:
        raise LogicError("Trump suit not set")
    if self.rank == jack:
        if self.suit == ctx.trump_suit:
            bower = find_bower(right, ctx.trump_suit)
        elif self.suit == ctx.trump_suit.next_suit():
            bower = find_bower(left, ctx.trump_suit)
    return bower or self

def realcard(self, ctx: GameCtxMixin) -> Card:
    """Inverse of `effcard`, translates bowers back to the "real" card (i.e.
    the one in the deck)
    """
    if self.rank not in BOWER_RANKS:
        return self

    if self.suit != ctx.trump_suit:
        raise LogicError(f"Bower ({self}) does not match trump suit ({ctx.trump_suit})")
    if self.rank == right:
        return find_card(jack, ctx.trump_suit)
    elif self.rank == left:
        return find_card(jack, ctx.trump_suit.next_suit())

    raise LogicError(f"Don't know how to get realcard for {self}")

def beats(self, other: Card, ctx: GameCtxMixin) -> bool:
    """
    """
    if ctx.lead_card is None:
        raise LogicError("Lead card not set")
    lead_suit = ctx.lead_card.effsuit(ctx)

    ret = None
    # REVISIT: this is not very efficient or pretty, can probably do better by handling bower
    # suit and rank externally (e.g. replacing `Card`s in `Hand`s, once trump is declared)!!!
    self_follow  = self.effsuit(ctx) == lead_suit
    other_follow = other.effsuit(ctx) == lead_suit
    self_trump   = self.effsuit(ctx) == ctx.trump_suit
    other_trump  = other.effsuit(ctx) == ctx.trump_suit
    same_suit    = other.effsuit(ctx) == self.effsuit(ctx)

    if self_trump:
        ret = self.efflevel(ctx) > other.efflevel(ctx) if other_trump else True
    elif other_trump:
        ret = False
    elif not self_follow:
        if not other_follow:
            raise LogicError("Cannot evaluate if neither card follows lead or is trump")
        ret = False
    else:
        ret = self.efflevel(ctx) > other.efflevel(ctx) if same_suit else True
    return ret

setattr(Card, 'efflevel', efflevel)
setattr(Card, 'effsuit', effsuit)
setattr(Card, 'effcard', effcard)
setattr(Card, 'realcard', realcard)
setattr(Card, 'beats', beats)

########
# Hand #
########

SuitCards = dict[Suit, list[Card]]

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

    def __repr__(self):
        return repr(self.cards)

    def __str__(self):
        return '  '.join(str(c) for c in self.cards)

    def copy(self) -> 'Hand':
        return Hand(self.cards.copy())

    def copy_cards(self) -> list[Card]:
        return self.cards.copy()

    def append_card(self, card: Card) -> None:
        return self.cards.append(card)

    def remove_card(self, card: Card) -> None:
        return self.cards.remove(card)

    def cards_by_suit(self, ctx: GameCtxMixin, use_bowers: bool = False) -> SuitCards:
        """The `use_bowers` flag indicates whether to translate trump and next suit
        jacks to the equivalent `Bower` representation (may be used for analysis, but
        not playing, since not recognized by the `deal` module)
        """
        by_suit = {suit: [] for suit in SUITS}
        for card in self.cards:
            by_suit[card.effsuit(ctx)].append(card.effcard(ctx) if use_bowers else card)
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

Play = tuple[int, Card]  # (pos, card)

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
    pos:              int
    hand:             Hand
    turn_card:        Optional[Card]
    bids:             list[Bid]
    tricks:           list[Trick]
    contract:         Optional[Bid]
    caller_pos:       Optional[int]
    go_alone:         Optional[bool]
    def_alone:        Optional[bool]
    def_pos:          Optional[int]
    played_by_suit:   dict[Suit, Hand]
    unplayed_by_suit: dict[Suit, set[Card]]
    player_state:     dict

    @property
    def cur_trick(self) -> Trick:
        return self.tricks[-1]

    @property
    def bid_round(self) -> int:
        return 1 if len(self.bids) < 4 else 2

    @property
    def is_dealer(self) -> bool:
        return self.pos == 3

    @property
    def is_caller(self) -> bool:
        return self.pos == self.caller_pos

    @property
    def is_partner_caller(self) -> bool:
        return self.pos ^ 0x02 == self.caller_pos

    @property
    def is_next_call(self) -> bool:
        if not contract:
            raise LogicError("Cannot call before playing phase")
        next_suit = self.turn_card.suit.next_suit()
        return contract.suit == next_suit and len(self.bids) == 5

    @property
    def is_reverse_next(self) -> bool:
        if not contract:
            raise LogicError("Cannot call before playing phase")
        green_suits = self.turn_card.suit.green_suits()
        return contract.suit in green_suits and len(self.bids) == 6
