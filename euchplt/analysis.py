# -*- coding: utf-8 -*-

from .card import Suit, SUITS, Card, ace, jack, Bower
from .euchre import GameCtxMixin, SuitCards, Hand, DealState

###########
# SuitCtx #
###########

class SuitCtx(GameCtxMixin):
    """
    """
    suit: Suit

    def __init__(self, suit: Suit):
        self.suit = suit
        self.set_trump_suit(self.suit)

SUIT_CTX = {s: SuitCtx(s) for s in SUITS}

################
# HandAnalysis #
################

class HandAnalysis:
    """This class can be used for both bidding and playing
    """
    hand: Hand
    # first indexed by trump suit, then by individual suit
    suit_cards_by_trump: dict[Suit, SuitCards]

    def __init__(self, hand: Hand):
        self.hand = hand
        self.suit_cards_by_trump = {t: {} for t in SUITS}

    def get_suit_cards(self, trump_suit: Suit) -> SuitCards:
        if not self.suit_cards_by_trump[trump_suit]:
            ctx = SUIT_CTX[trump_suit]
            self.suit_cards_by_trump[trump_suit] = self.hand.cards_by_suit(ctx, use_bowers=True)
        return self.suit_cards_by_trump[trump_suit]

    def trump_cards(self, trump_suit: Suit, sort: bool = False) -> list[Card]:
        ret_cards = self.get_suit_cards(trump_suit)[trump_suit]
        if sort:
            ctx = SUIT_CTX[trump_suit]
            ret_cards.sort(key=lambda c: c.efflevel(ctx), reverse=True)
        return ret_cards

    def off_aces(self, trump_suit: Suit) -> list[Card]:
        aces = []
        for card in self.hand.cards:
            if card.rank == ace and card.suit != trump_suit:
                aces.append(card)
        return aces

    def bowers(self, trump_suit: Suit) -> list[Bower]:
        trumps = self.trump_cards(trump_suit)
        return [c for c in trumps if isinstance(c, Bower)]

    def voids(self, trump_suit: Suit) -> list[Suit]:
        suit_cards = self.get_suit_cards(trump_suit)
        return [suit for suit, cards in suit_cards.items() if len(cards) == 0]

    def cards_by_level(self, suit: Suit, offset_trump: bool = False) -> list[Card]:
        ctx = SUIT_CTX[suit]
        by_level = self.hand.copy_cards()
        by_level.sort(key=lambda c: c.efflevel(ctx, offset_trump), reverse=True)
        return by_level

################
# PlayAnalysis #
################

class PlayAnalysis:
    """
    """
    deal:          DealState
    ctx:           GameCtxMixin
    hand_analysis: HandAnalysis

    def __init__(self, deal: DealState):
        self.deal          = deal
        self.ctx           = SUIT_CTX[deal.contract.suit]
        self.hand_analysis = HandAnalysis(deal.hand)

    def trump_cards(self, sort: bool = False) -> list[Card]:
        return self.hand_analysis.trump_cards(self.ctx.suit, sort)

    def off_aces(self) -> list[Card]:
        return self.hand_analysis.off_aces(self.ctx.suit)

    def bowers(self) -> list[Card]:
        return self.hand_analysis.bowers(self.ctx.suit)

    def follow_cards(self, lead_card: Card, sort: bool = False) -> list[Card]:
        lead_suit = lead_card.effsuit(self.ctx)
        ret_cards = self.deal.hand.cards_by_suit(self.ctx)[lead_suit]
        if sort:
            ret_cards.sort(key=lambda c: c.efflevel(self.ctx), reverse=True)
        return ret_cards

    def cards_by_level(self, offset_trump: bool = False) -> list[Card]:
        return self.hand_analysis.cards_by_level(self.ctx.suit, offset_trump)
