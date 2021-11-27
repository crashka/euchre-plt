# -*- coding: utf-8 -*-

from .card import Suit, SUITS, Card, ace, jack
from .euchre import GameCtxMixin, Hand, DealState

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
    """
    """
    hand: Hand

    def __init__(self, hand: Hand):
        self.hand = hand

    def trump_cards(self, trump_suit: Suit, sort: bool = False) -> list[Card]:
        ctx = SUIT_CTX[trump_suit]
        ret_cards = self.hand.cards_by_suit(ctx)[trump_suit]
        if sort:
            ret_cards.sort(key=lambda c: c.efflevel(ctx), reverse=True)
        return ret_cards

    def off_aces(self, trump_suit: Suit) -> list[Card]:
        aces = []
        for card in self.hand.cards:
            if card.rank == ace and card.suit != trump_suit:
                aces.append(card)
        return aces

    def bowers(self, trump_suit: Suit) -> list[Card]:
        ctx = SUIT_CTX[trump_suit]
        ret_bowers = []
        for card in self.hand.cards:
            if card.rank == jack and card.effsuit(ctx) == trump_suit:
                ret_bowers.append(card)
        return ret_bowers

    def cards_by_level(self, suit: Suit, offset_trump: bool = False) -> list[Card]:
        ctx = SUIT_CTX[suit]
        by_rank = self.hand.copy_cards()
        by_rank.sort(key=lambda c: c.efflevel(ctx, offset_trump), reverse=True)
        return by_rank

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
