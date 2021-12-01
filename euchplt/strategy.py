#!/usr/bin/env python
# -*- coding: utf-8 -*-

from random import Random

from .core import LogicError
from .card import SUITS, Card, jack
from .euchre import Bid, PASS_BID, defend_suit, Trick, DealState
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
    conservative (though we add an `aggressive` option)
    """
    aggressive: bool

    def __init__(self, aggressive: bool = False):
        super().__init__()
        self.aggressive = aggressive

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
        play_pos = len(trick.plays)  # zero-based

        # lead highest card
        if play_pos == 0:
            for card in by_level:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        lead_card = trick.plays[0][1]
        follow_cards = analysis.follow_cards(lead_card, sort=True)

        # partner is winning, try and duck (unless `aggressive` third hand)
        if trick.winning_pos == deal.pos ^ 0x02:
            take_order = 1 if (self.aggressive and play_pos == 2) else -1
            cards = follow_cards if follow_cards else by_level
            for card in cards[::-1]:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        # opponents winning, take trick if possible
        cards = follow_cards if follow_cards else by_level
        # second/third hand take low unless `aggressive` specified (fourth
        # hand always take low)
        take_order = 1 if (self.aggressive and play_pos < 3) else -1
        for card in cards[::take_order]:
            if card in valid_plays and card.beats(trick.winning_card, trick):
                return card
        # can't take, so just duck or slough off
        for card in cards[::-1]:
            if card in valid_plays:
                return card
        raise LogicError("No valid card to play")

#################
# StrategySmart #
#################

class StrategySmart(Strategy):
    """
    """
    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """
                        9 10  J  Q  K  A  L  R
        trump_values = [0, 0, 0, 1, 2, 4, 7, 10]
        suit_values  = [0, 0, 0, 1, 5, 10]

        scoring aspects (multiple by coefficients):
          - trump strength
          - max(off-suit strength)
          - num trump
          - off-aces
          - voids

        round 1:
          - non-dealer:
            - compute score (turn suit)
            - adjust for turn card (partner vs. opp)
            - bid if score > round1_thresh (by position)
          - dealer:
            - compute scores (turn suit) for turn + each discard (including turn)
            - bid if max(score) > round1_thresh (dealer position)
        round 2:
          - all players:
            - compute score for each non-turn suit
            - bid if max(score) > round2_thresh (by position)
        """
        raise NotImplementedError("Not yet implemented")

    def discard(self, deal: DealState) -> Card:
        """
        Note that the turn card is already in the player's hand (six cards now) when
        this is called

        logic:
          - all trump case (discard lowest)
          - create void
            - don't discard singleton ace (exception case?)
            - prefer next or green suit?
            - "always void next if loner called from pos 2"[???]
          - create doubleton
            - perhaps only do if high card in suit is actually viable (>=Q)
          - discard from next
            - don't unguard doubleton king or break up A-K
          - discard lowest
            - avoid unguarding doubleton king, while making sure that A-K doubleton
              takes precedence (if also present)
            - worry about off-ace vs. low trump?
            - choose between green suit doubletons?
        """
        raise NotImplementedError("Not yet implemented")

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """
        lead card plays:
          - lead_last_card
          - next_call_lead
          - draw_trump
          - lead_off_ace
          - lead_to_partner_call
          - lead_to_create_void
          - lead_suit_winner
          - lead_low_non_trump
          - lead_low_from_long_suit
          - lead_random_card
        follow card plays:
          - play_last_card
          - follow_suit_low
          - throw_off_to_create_void
          - throw_off_low
          - play_low_trump
          - follow_suit_high
          - trump_low
          - play_random_card
        configurable logic for:
          - init_lead
          - subseq_lead
          - part_winning
          - opp_winning

        logic for next_call_lead (especially if calling with weaker hand...):
          - The best first lead on a next call is a small trump, this is especially
            true if you hold an off-suit Ace. By leading a small trump you stand the
            best chance of hitting your partner's hand. Remember, the odds are that
            he will have at least one bower in his hand.
          - Leading the right may not be the best move. Your partner may only have
            one bower in his hand and you don't want them to clash. When you are
            holding a right/ace combination it's usually best to lead the ace. If
            the other bower has been turned down, then it is okay to lead the right.
          - In a hand where you only hold two small cards in next but no power, try
            leading an off suit that you think your partner may be able to trump.
            You may need the trump to make your point.
          - If your partner calls next and leads a trump, DO NOT lead trump back.
        """
        raise NotImplementedError("Not yet implemented")

##############
# StrategyML #
##############

class StrategyML(Strategy):
    """
    """
    pass
