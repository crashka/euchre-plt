#!/usr/bin/env python
# -*- coding: utf-8 -*-

from random import Random

from .core import LogicError
from .card import SUITS, Card, jack
from .euchre import Bid, PASS_BID, defend_suit, Hand, Trick, DealState
from .analysis import HandAnalysis, PlayAnalysis

############
# Strategy #
############

class Strategy:
    """
    """
    def __str__(self):
        return self.__class__.__name__

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """
        """
        raise NotImplementedError("Can't call abstract method")

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called
        """
        raise NotImplementedError("Can't call abstract method")

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """
        """
        raise NotImplementedError("Can't call abstract method")

##################
# StrategyRandom #
##################

class StrategyRandom(Strategy):
    """
    """
    random: Random

    def __init__(self, seed: int = None):
        super().__init__()
        self.random = Random(seed)

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            alone = self.random.random() < 0.10
            return Bid(defend_suit, alone)

        bid_no = len(deal.bids)
        do_bid = self.random.random() < 1 / (9 - bid_no)
        if do_bid:
            if deal.bid_round == 1:
                alone = self.random.random() < 0.10
                return Bid(deal.turn_card.suit, alone)
            else:
                alone = self.random.random() < 0.20
                biddable_suits = [s for s in SUITS if s != deal.turn_card.suit]
                return Bid(self.random.choice(biddable_suits), alone)
        else:
            return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.random.choice(deal.hand.cards)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.random.choice(valid_plays)

##################
# StrategySimple #
##################

class StrategySimple(Strategy):
    """Represents minimum logic for passable play, very basic strategy, fairly
    conservative
    """
    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        analysis   = HandAnalysis(deal.hand)
        bid_suit   = None
        alone      = False
        num_trump  = None
        off_aces   = None
        num_bowers = None

        if def_bid:
            # defend alone if 4 or more trump, or 3 trump and off-ace
            num_trump = len(analysis.trump_cards(deal.contract.suit))
            off_aces  = analysis.off_aces(deal.contract.suit)
            if num_trump >= 4 or (num_trump == 3 and len(off_aces) > 0):
                alone = True
            return Bid(defend_suit, alone)

        if deal.bid_round == 1:
            # bid if 3 or more trump, and bower/off-ace
            num_trump  = len(analysis.trump_cards(deal.turn_card.suit))
            off_aces   = analysis.off_aces(deal.turn_card.suit)
            num_bowers = len(analysis.bowers(deal.turn_card.suit))
            if deal.is_dealer:
                num_trump += 1
                if deal.turn_card.rank == jack:
                    num_bowers += 1
                if num_trump >= 2 and len(off_aces) > 0:
                    bid_suit = deal.turn_card.suit
            elif num_trump >= 3 and (off_aces or num_bowers > 0):
                bid_suit = deal.turn_card.suit
        else:
            # bid if 3 or more trump in any suit, and bower/off-ace
            for suit in SUITS:
                if suit == deal.turn_card.suit:
                    continue
                num_trump  = len(analysis.trump_cards(suit))
                off_aces   = analysis.off_aces(suit)
                num_bowers = len(analysis.bowers(suit))
                if num_trump >= 3 and (off_aces or num_bowers > 0):
                    bid_suit = suit
                    break

        if bid_suit:
            assert num_trump is not None
            assert off_aces is not None
            assert num_bowers is not None
            # go alone if 4 or more trump, or 3 trump and off-ace; must have at least
            # one bower (right may be buried, so not required)
            if num_trump >= 4 and num_bowers > 0:
                alone = True
            elif num_trump == 3 and num_bowers > 0 and off_aces:
                alone = True
            return Bid(bid_suit, alone)

        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        analysis = PlayAnalysis(deal)
        by_level = analysis.cards_by_level(offset_trump=True)
        return by_level[-1]

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        analysis = PlayAnalysis(deal)
        by_level = analysis.cards_by_level(offset_trump=True)

        if len(trick.plays) == 0:
            # lead highest card
            for card in by_level:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        lead_card = trick.plays[0][1]
        follow_cards = analysis.follow_cards(lead_card, sort=True)

        # duck (or at least try) if partner is winning trick
        if trick.winning_pos == deal.pos ^ 0x02:
            cards = follow_cards if follow_cards else by_level
            for card in cards[::-1]:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        # opponents winning, take trick if possible
        cards = follow_cards if follow_cards else by_level
        for card in cards[::-1]:
            if card in valid_plays and card.beats(trick.winning_card, trick):
                return card
        # can't take, so just duck or slough off
        for card in cards[::-1]:
            if card in valid_plays:
                return card
        raise LogicError("No valid card to play")

####################
# StrategyStandard #
####################

class StrategyStandard(Strategy):
    """
    """
    pass

##############
# StrategyML #
##############

class StrategyML(Strategy):
    """
    """
    pass
