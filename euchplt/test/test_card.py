# -*- coding: utf-8 -*-

from euchplt.card import RANKS, BOWERS, ALLRANKS, SUITS, CARDS

def test_card_basic():
    assert len(RANKS)    == 6
    assert len(BOWERS)   == 2
    assert len(ALLRANKS) == 8
    assert len(SUITS)    == 4
    assert len(CARDS)    == 24
