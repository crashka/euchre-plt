# -*- coding: utf-8 -*-

from ..core import LogicError
from ..card import SUITS, Card, jack
from ..euchre import Bid, PASS_BID, defend_suit, Trick, DealState
from ..analysis import HandAnalysis, PlayAnalysis
from .base import Strategy

##################
# StrategySimple #
##################

class StrategySimple(Strategy):
    """Represents minimum logic for passable play--very basic strategy, fairly
    conservative (though we add several options for more aggressive play).

    ``aggressive`` parameter bit fields:
    
    - partner is winning, but play high (pre-emptive) from the third seat rather than duck
    - take high (if possible) from second or third seat, rather than lower take (e.g. use
      A instead of Q on a lead of 9)

    TODO (maybe): parameterize some of the magic numbers in this code!?!?
    """
    # this is actually a bitfield, see individual switches below
    aggressive: int = 0x0

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        analysis   = HandAnalysis(deal.hand)
        turn_suit  = deal.turn_card.suit
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
            num_trump  = len(analysis.trump_cards(turn_suit))
            off_aces   = analysis.off_aces(turn_suit)
            num_bowers = len(analysis.bowers(turn_suit))
            if deal.is_dealer:
                num_trump += 1
                if deal.turn_card.rank == jack:
                    num_bowers += 1
                if num_trump >= 2 and len(off_aces) > 0:
                    bid_suit = turn_suit
            elif num_trump >= 3 and (off_aces or num_bowers > 0):
                bid_suit = turn_suit
        else:
            assert deal.bid_round == 2
            # bid if 3 or more trump in any suit, and bower/off-ace
            for suit in SUITS:
                if suit == turn_suit:
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

        # lead highest card
        if deal.play_seq == 0:
            for card in by_level:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        lead_card = trick.plays[0][1]
        follow_cards = analysis.follow_cards(lead_card)

        # partner is winning, try and duck (unless `aggressive & 0x01` third hand)
        if trick.winning_pos == deal.pos ^ 0x02:
            take_order = 1 if (self.aggressive & 0x01 and deal.play_seq == 2) else -1
            cards = follow_cards if follow_cards else by_level
            for card in cards[::take_order]:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        # opponents winning, take trick if possible
        cards = follow_cards if follow_cards else by_level
        # second/third hand take low unless `aggressive & 0x02` specified (fourth hand
        # always take low)
        take_order = 1 if (self.aggressive & 0x02 and deal.play_seq < 3) else -1
        for card in cards[::take_order]:
            if card in valid_plays and card.beats(trick.winning_card, trick):
                return card
        # can't take, so just duck or slough off
        for card in cards[::-1]:
            if card in valid_plays:
                return card
        raise LogicError("No valid card to play")
