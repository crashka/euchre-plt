# -*- coding: utf-8 -*-

"""See __init__.py for module-level documentation
"""

from ..card import Suit, SUITS, Card, ace, Bower
from ..euchre import GameCtxMixin, SuitCards, Hand, DealState

###########
# SuitCtx #
###########

class SuitCtx(GameCtxMixin):
    """Wrapper for ``GameCtxMixin`` for usage within the module (treating the base class as
    abstract).  See ``SUIT_CTX``.
    """
    suit: Suit

    def __init__(self, suit: Suit):
        self.suit = suit
        self.set_trump_suit(self.suit)

# convenience dict used to set context for `HandAnalysis` methods and `PlayAnalysis`
# instantiations
SUIT_CTX: dict[Suit, SuitCtx] = {s: SuitCtx(s) for s in SUITS}

################
# HandAnalysis #
################

class HandAnalysis:
    """This class provides helper methods for evaluating hands, typically by extracting
    useful subsets (i.e. lists) of cards, given a trump suit context.  Counts can then be
    easily derived using ``len()``.  This class is generally only used directly in the
    bidding process, during which the underlying hand does not change (there is no caching
    of results).

    Note that these calls still work if/as the hand changes (e.g. cards are swapped and/or
    played), thus ``PlayAnalysis`` contains wrapper methods which automatically pass in the
    trump suit context (since it will already be known for the deal).
    """
    hand: Hand
    # first indexed by trump suit, then by individual suit
    suit_cards_by_trump: dict[Suit, SuitCards]

    def __init__(self, hand: Hand):
        self.hand = hand
        self.suit_cards_by_trump = {t: {} for t in SUITS}

    def get_suit_cards(self, trump_suit: Suit) -> SuitCards:
        """Return list of cards indexed by suit.  Note that this always translates jacks
        into bowers, and sorts by descending rank/level within each suit.
        """
        if not self.suit_cards_by_trump[trump_suit]:
            ctx = SUIT_CTX[trump_suit]
            by_suit = self.hand.cards_by_suit(ctx, use_bowers=True)
            for suit, cards in by_suit.items():
                cards.sort(key=lambda c: c.efflevel(ctx), reverse=True)
            self.suit_cards_by_trump[trump_suit] = by_suit
        return self.suit_cards_by_trump[trump_suit]

    def trump_cards(self, trump_suit: Suit) -> list[Card]:
        """Return list of trump cards, sorted by descending rank.
        """
        return self.get_suit_cards(trump_suit)[trump_suit]

    def next_suit_cards(self, trump_suit: Suit) -> list[Card]:
        """Return list of cards in "next" suit, sorted by descending rank.
        """
        return self.get_suit_cards(trump_suit)[trump_suit.next_suit()]

    def green_suit_cards(self, trump_suit: Suit) -> tuple[list[Card], ...]:
        """Returns tuple of card lists, ordered by decreasing length (and descending rank
        within each suit).
        """
        green_suits = trump_suit.green_suits()
        suit_cards  = tuple(self.get_suit_cards(trump_suit)[s] for s in green_suits)
        is_ordered  = len(suit_cards[0]) >= len(suit_cards[1])
        return suit_cards if is_ordered else suit_cards[::-1]

    def off_aces(self, trump_suit: Suit) -> list[Card]:
        """Return list of off-aces, in no particular order.
        """
        return [c for c in self.hand.cards if c.rank == ace and c.suit != trump_suit]

    def bowers(self, trump_suit: Suit) -> list[Bower]:
        """Return list of bowers, in order of descending rank.
        """
        trumps = self.trump_cards(trump_suit)
        return [c for c in trumps if isinstance(c, Bower)]

    def voids(self, trump_suit: Suit) -> list[Suit]:
        """Return list of suits that are void in the hand.
        """
        suit_cards = self.get_suit_cards(trump_suit)
        return [suit for suit, cards in suit_cards.items() if len(cards) == 0]

    def singleton_cards(self, trump_suit: Suit) -> list[Card]:
        """Return the singleton cards themselves; the singleton suits are implied.
        """
        suit_cards = self.get_suit_cards(trump_suit)
        return [cards[0] for cards in suit_cards.values() if len(cards) == 1]

    def cards_by_level(self, trump_suit: Suit, offset_trump: bool = False) -> list[Card]:
        """Return cards by descending level.  ``offset_trump=True`` sorts all trump higher
        than all non-trump.  Note, this does NOT currently translate jacks into bowers,
        though recognizes them by effective level and always sorts them highest.
        """
        ctx = SUIT_CTX[trump_suit]
        by_level = self.hand.copy_cards()
        by_level.sort(key=lambda c: c.efflevel(ctx, offset_trump), reverse=True)
        return by_level

################
# PlayAnalysis #
################

class PlayAnalysis:
    """This class provides helper methods for evaluating hands during the play process.
    It contains wrappers for useful ``HandAnalysis`` methods (which will reflect the current
    state of the hand in the deal), as well as additional functions helpful during play.
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

    def get_suit_cards(self) -> SuitCards:
        """Wrapper method for ``HandAnalysis.get_suit_cards()``
        """
        return self.hand_analysis.get_suit_cards(self.ctx.suit)

    def trump_cards(self) -> list[Card]:
        """Wrapper method for ``HandAnalysis.trump_cards()``
        """
        return self.hand_analysis.trump_cards(self.ctx.suit)

    def next_suit_cards(self) -> list[Card]:
        """Wrapper method for ``HandAnalysis.next_suit_cards()``
        """
        return self.hand_analysis.next_suit_cards(self.ctx.suit)

    def green_suit_cards(self) -> tuple[list[Card], ...]:
        """Wrapper method for ``HandAnalysis.green_suit_cards()``
        """
        return self.hand_analysis.green_suit_cards(self.ctx.suit)

    def off_aces(self) -> list[Card]:
        """Wrapper method for ``HandAnalysis.off_aces()``
        """
        return self.hand_analysis.off_aces(self.ctx.suit)

    def bowers(self) -> list[Card]:
        """Wrapper method for ``HandAnalysis.bowers()``
        """
        return self.hand_analysis.bowers(self.ctx.suit)

    def follow_cards(self, lead_card: Card) -> list[Card]:
        """Return the list of cards that follow the lead card suit.  Note, this does NOT
        currently translate jacks into bowers, so cards from this list can be returned
        directly by ``play_card()``.
        """
        lead_suit = lead_card.effsuit(self.ctx)
        return self.hand.cards_by_suit(self.ctx, use_bowers=False)[lead_suit]

    def singleton_cards(self) -> list[Card]:
        """Return the singleton cards themselves; the singleton suits are implied.
        """
        return self.hand_analysis.singleton_cards(self.ctx.suit)

    def cards_by_level(self, offset_trump: bool = False) -> list[Card]:
        """Return cards by descending level.  Note, this does NOT currently translate
        jacks into bowers (based on the HandAnalysis implementation), so cards from this
        list can be returned directly by ``play_card()``.
        """
        return self.hand_analysis.cards_by_level(self.ctx.suit, offset_trump)

    def unplayed_by_suit(self) -> dict[Suit, list[Card]]:
        """Recast card sets as lists, so we can order them by descending level within each
        suit.  Note, this does NOT currently translate jacks into bowers, so cards from
        this list can be returned directly by ``play_card()``.
        """
        card_set_iter = self.deal.unplayed_by_suit.items()
        suit_cards = {suit: list(card_set) for suit, card_set in card_set_iter}
        for suit, cards in suit_cards.items():
            cards.sort(key=lambda c: c.efflevel(self.ctx), reverse=True)
        return suit_cards

    def suit_winners(self) -> dict[Suit, Card | None]:
        """Return the highest outstanding card for each suit, or None if no cards
        remaining.
        """
        return {suit: cards[0] if cards else None
                for suit, cards in self.unplayed_by_suit().items()}

    def my_winners(self) -> list[Card]:
        """Return flat list of non-trump suit high cards in the current hand; sort by card
        level descending across suits.
        """
        winners = [card for suit, card in self.suit_winners().items()
                   if card in self.hand and card.suit != self.ctx.suit]
        winners.sort(key=lambda c: c.efflevel(self.ctx))
        return winners

    def trumps_played(self) -> list[Card]:
        """These are the cards that have been played by anyone.  Note, this DOES translate
        jacks into bowers, so that bower levels and ranks can be used; return list is NOT
        sorted.
        """
        cards = self.deal.played_by_suit[self.ctx.suit].cards
        return [card.effcard(self.ctx) for card in cards]

    def trumps_unplayed(self) -> list[Card]:
        """Note, this DOES translate jacks into bowers, so that bower levels and ranks can
        be used; return list is NOT sorted.
        """
        card_set = self.deal.unplayed_by_suit[self.ctx.suit]
        return [card.effcard(self.ctx) for card in card_set]

    def trumps_missing(self) -> list[Card]:
        """Returns trump cards not yet played and not in the current hand-- in other
        words, those that we need to account for.  Note, this DOES translate jacks into
        bowers, so that bower levels and ranks can be used, the return list IS sorted.
        """
        # FIX: this is really bad, translating back and forth between set (for using
        # `difference`) and list (for sorting)--and for only five freaking elements,
        # MAX--really, really stupid!!!
        unplayed = set(self.trumps_unplayed())
        missing = list(unplayed.difference(self.trump_cards()))
        missing.sort(key=lambda c: c.efflevel(self.ctx), reverse=True)
        return missing
