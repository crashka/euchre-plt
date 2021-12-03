# -*- coding: utf-8 -*-

import pytest

from euchplt.card import RANKS, BOWER_RANKS, ALL_RANKS, SUITS, CARDS, BOWERS
from euchplt.card import Card, Bower, ace, jack, ten, left, right, clubs, diamonds, spades
from euchplt.card import find_card, find_bower, get_deck

def test_static_lists():
    assert len(RANKS)       == 6
    assert len(BOWER_RANKS) == 2
    assert len(ALL_RANKS)   == 8
    assert len(SUITS)       == 4
    assert len(CARDS)       == 24
    assert len(BOWERS)      == 8

def test_find_card():
    card = find_card(ace, diamonds)
    assert type(card) == Card
    assert card.rank == ace
    assert card.suit == diamonds

    # finding bowers should always raise an exception
    with pytest.raises(IndexError):
        _ = find_card(left, clubs)
    with pytest.raises(IndexError):
        _ = find_card(right, spades)

def test_find_bower():
    bower = find_bower(left, diamonds)
    assert type(bower) == Bower
    assert bower.rank == left
    assert bower.suit == diamonds

    bower = find_bower(right, spades)
    assert type(bower) == Bower
    assert bower.rank == right
    assert bower.suit == spades

    # two different failure modes for mis-use, depending on
    # whether non-bower card index happens to be in bounds
    with pytest.raises(IndexError):
        _ = find_bower(ten, diamonds)

    bower = find_bower(ace, diamonds)  # errant success
    assert not (bower.rank == ten)     # prove the error

def test_get_deck():
    deck = get_deck()
    assert len(deck) == len(CARDS)
    assert set(deck) == set(CARDS)
