# -*- coding: utf-8 -*-

from typing import Optional

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
        """Note that this always translates jacks into bowers, and sorts by
        descending rank/level within each suit
        """
        if not self.suit_cards_by_trump[trump_suit]:
            ctx = SUIT_CTX[trump_suit]
            by_suit = self.hand.cards_by_suit(ctx, use_bowers=True)
            for suit, cards in by_suit.items():
                cards.sort(key=lambda c: c.efflevel(ctx), reverse=True)
            self.suit_cards_by_trump[trump_suit] = by_suit
        return self.suit_cards_by_trump[trump_suit]

    def trump_cards(self, trump_suit: Suit) -> list[Card]:
        return self.get_suit_cards(trump_suit)[trump_suit]

    def green_suit_cards(self, trump_suit: Suit) -> tuple[list[Card]]:
        """Returns tuple of Card lists, ordered by decreasing length
        """
        green_suits = trump_suit.green_suits()
        suit_cards  = tuple(self.get_suit_cards(trump_suit)[s] for s in green_suits)
        is_ordered  = len(suit_cards[0]) >= len(suit_cards[1])
        return suit_cards if is_ordered else suit_cards[::-1]

    def off_aces(self, trump_suit: Suit) -> list[Card]:
        return [c for c in self.hand.cards if c.rank == ace and c.suit != trump_suit]

    def bowers(self, trump_suit: Suit) -> list[Bower]:
        trumps = self.trump_cards(trump_suit)
        return [c for c in trumps if isinstance(c, Bower)]

    def voids(self, trump_suit: Suit) -> list[Suit]:
        suit_cards = self.get_suit_cards(trump_suit)
        return [suit for suit, cards in suit_cards.items() if len(cards) == 0]

    def singleton_cards(self, trump_suit: Suit) -> list[Card]:
        """Return the singleton cards themselves; the singleton suits are implied
        """
        suit_cards = self.get_suit_cards(trump_suit)
        return [cards[0] for cards in suit_cards.values() if len(cards) == 1]

    def cards_by_level(self, trump_suit: Suit, offset_trump: bool = False) -> list[Card]:
        """Note, this does NOT currently translate jacks into bowers
        """
        ctx = SUIT_CTX[trump_suit]
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
    hand:          Hand
    hand_analysis: HandAnalysis

    def __init__(self, deal: DealState):
        self.deal          = deal
        self.ctx           = SUIT_CTX[deal.contract.suit]
        self.hand          = deal.hand
        self.hand_analysis = HandAnalysis(self.hand)

    def trump_cards(self) -> list[Card]:
        return self.hand_analysis.trump_cards(self.ctx.suit)

    def green_suit_cards(self) -> tuple[list[Card]]:
        return self.hand_analysis.green_suit_cards(self.ctx.suit)

    def off_aces(self) -> list[Card]:
        return self.hand_analysis.off_aces(self.ctx.suit)

    def bowers(self) -> list[Card]:
        return self.hand_analysis.bowers(self.ctx.suit)

    def follow_cards(self, lead_card: Card) -> list[Card]:
        """Note, this does NOT currently translate jacks into bowers, so cards
        from this list can be returned by `play_card()`
        """
        lead_suit = lead_card.effsuit(self.ctx)
        return self.hand.cards_by_suit(self.ctx)[lead_suit]

    def singleton_cards(self) -> list[Card]:
        """Return the singleton cards themselves; the singleton suits are implied
        """
        return self.hand_analysis.singleton_cards(self.ctx.suit)

    def cards_by_level(self, offset_trump: bool = False) -> list[Card]:
        """Note, this does NOT currently translate jacks into bowers (based on
        the HandAnalysis implemention), so cards from this list can be returned
        by `play_card()`
        """
        return self.hand_analysis.cards_by_level(self.ctx.suit, offset_trump)

    def unplayed_by_suit(self) -> dict[Suit, list[Card]]:
        """Recast card sets as lists, so we can order them by descending level
        within each suit.  Note, this does NOT currently translate jacks into
        bowers, so cards from this list can be returned by `play_card()`
        """
        card_set_iter = self.deal.unplayed_by_suit.items()
        suit_cards = {suit: list(card_set) for suit, card_set in card_set_iter}
        for suit, cards in suit_cards.items():
            cards.sort(key=lambda c: c.efflevel(self.ctx), reverse=True)
        return suit_cards

    def suit_winners(self) -> dict[Suit, Optional[Card]]:
        """Return the highest outstanding card for each suit, or None if
        no cards remaining
        """
        return {suit: cards[0] if cards else None
                for suit, cards in self.unplayed_by_suit().items()}

    def my_winners(self) -> list[Card]:
        """Return flat list of non-trump suit high cards in the current hand;
        sort by card level descending across suits
        """
        winners = [card for suit, card in self.suit_winners().items()
                   if card in self.hand and card.suit != self.ctx.suit]
        winners.sort(key=lambda c: c.efflevel(self.ctx))
        return winners

    def trumps_played(self) -> list[Card]:
        """These are the cards that have been played by anyone.  Note, this
        DOES translate jacks into bowers, so that bower levels and ranks can
        be used; return list is NOT sorted
        """
        cards = self.deal.played_by_suit[self.ctx.suit].cards
        return [card.effcard(self.ctx) for card in cards]

    def trumps_unplayed(self) -> list[Card]:
        """Note, this DOES translate jacks into bowers, so that bower levels and
        ranks can be used; return list is NOT sorted
        """
        card_set = self.deal.unplayed_by_suit[self.ctx.suit]
        return [card.effcard(self.ctx) for card in card_set]

    def trumps_missing(self) -> list[Card]:
        """Returns trump cards not yet played and not in the currrent hand--
        in other words, those that we need to account for.  Note, this DOES
        translate jacks into bowers, so that bower levels and ranks can be
        used, the return list IS sorted
        """
        # FIX: this is really bad, translating back and forth between set (for
        # the `difference` function) and list (for the ordering)--and for only
        # five freaking elements, MAX--really, really stupid!!!
        unplayed = set(self.trumps_unplayed())
        missing = list(unplayed.difference(self.trump_cards()))
        missing.sort(key=lambda c: c.efflevel(self.ctx), reverse=True)
        return missing
