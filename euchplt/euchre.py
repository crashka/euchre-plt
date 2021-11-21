# -*- coding: utf-8 -*-

from .card import SUITS, Suit, Card, jack, right, left

################
# GameCtxMixin #
################

class GameCtxMixin(object):
    """
    """
    def set_context(self, trump_suit: Suit, lead_card: Card):
        """
        param trump_suit: Suit
        param lead_card:  Card
        """
        self._trump_suit = trump_suit
        self._lead_card  = lead_card

    @property
    def trump_suit(self) -> Suit:
        try:
            return self._trump_suit
        except AttributeError:
            raise RuntimeError("'set_context' never called")

    @property
    def lead_card(self) -> Card:
        try:
            return self._lead_card
        except AttributeError:
            raise RuntimeError("'set_context' never called")

################
# augment Suit #
################

def opp_suit(self, ctx: GameCtxMixin) -> Suit:
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
    is_jack  = self.rank == jack
    is_trump = self.suit == ctx.trump_suit
    is_opp   = self.suit == ctx.trump_suit.opp_suit(ctx)
    if is_jack:
        if is_trump:
            return right.level
        elif is_opp:
            return left.level
    return self.level

def effsuit(self, ctx: GameCtxMixin) -> Suit:
    """
    """
    is_jack = self.rank == jack
    is_opp  = self.suit == ctx.trump_suit.opp_suit(ctx)
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
