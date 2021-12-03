# -*- coding: utf-8 -*-

import pytest

from euchplt.core import LogicError
from euchplt.card import ace, king, queen, jack, ten, nine, right, left
from euchplt.card import clubs, diamonds, hearts, spades, find_card, find_bower
from euchplt.euchre import GameCtxMixin, Hand
from euchplt.analysis import HandAnalysis

def test_hand_analysis():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ace,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])

    analysis = HandAnalysis(hand)
    trump_suit = diamonds
    right_bower = find_bower(right, trump_suit)
    left_bower = find_bower(left, trump_suit)

    suit_cards = analysis.get_suit_cards(trump_suit)
    assert len(suit_cards[clubs]) == 1
    assert set(suit_cards[clubs]) == {card3}
    assert len(suit_cards[diamonds]) == 4
    assert set(suit_cards[diamonds]) == {card1, card2, right_bower, left_bower}
    assert len(suit_cards[hearts]) == 0
    assert len(suit_cards[spades]) == 0

    trump_cards = analysis.trump_cards(trump_suit)
    assert len(trump_cards) == 4
    assert set(trump_cards) == {card1, card2, right_bower, left_bower}
    trump_cards = analysis.trump_cards(trump_suit, sort=True)
    assert trump_cards[0] == right_bower

    off_aces = analysis.off_aces(trump_suit)
    assert set(off_aces) == {card3}

    bowers = analysis.bowers(trump_suit)
    assert set(bowers) == {right_bower, left_bower}

    voids = analysis.voids(trump_suit)
    assert set(voids) == {hearts, spades}
