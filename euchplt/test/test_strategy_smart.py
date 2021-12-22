# -*- coding: utf-8 -*-

from euchplt.core import cfg
from euchplt.card import ace, king, queen, jack, ten, nine
from euchplt.card import clubs, diamonds, hearts, spades, find_card
from euchplt.euchre import Hand
from euchplt.analysis import HandAnalysisSmart
from euchplt.strategy import StrategySmart

cfg.load('test_config.yml')

def test_strategy_smart():
    strat = StrategySmart()

def test_hand_analysis_smart():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ace,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])

    analysis = HandAnalysisSmart(hand)
    trump_suit = diamonds

    hand_strength = analysis.hand_strength(trump_suit)
