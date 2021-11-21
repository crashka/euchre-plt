# -*- coding: utf-8 -*-

import pytest

from euchplt.card import SUITS, CARDS, ace, king, queen, jack, ten
from euchplt.card import diamonds, hearts, spades, find_card
from euchplt.euchre import GameCtxMixin

class DummyContext(GameCtxMixin):
    pass

def test_game_context():
    mysuit = SUITS[0]
    mycard = CARDS[0]

    ctx = DummyContext()
    ctx.set_context(mysuit, mycard)
    assert ctx.trump_suit == mysuit
    assert ctx.lead_card == mycard

def test_game_context_unset():
    ctx = DummyContext()
    with pytest.raises(RuntimeError):
        _ = ctx.trump_suit
    with pytest.raises(RuntimeError):
        _ = ctx.lead_card

def test_card_beats():
    """Note, we're staying away from bowers in this test
    """
    refcard = find_card(king, diamonds)
    refsuit = refcard.suit

    ctx = DummyContext()
    ctx.set_context(refsuit, refcard)

    # test within trump suit
    bigger_trump = find_card(ace, diamonds)
    assert bigger_trump.beats(refcard, ctx)
    smaller_trump = find_card(queen, diamonds)
    assert not smaller_trump.beats(refcard, ctx)

    # test against non-trump
    bigger_non_trump = find_card(ace, hearts)
    assert not bigger_non_trump.beats(refcard, ctx)
    smaller_non_trump = find_card(queen, hearts)
    assert not smaller_non_trump.beats(refcard, ctx)

    # test non-trump against trump (change `refcard`)
    refcard = find_card(king, hearts)
    assert refcard.suit != refsuit
    ctx.set_context(refsuit, refcard)
    assert bigger_trump.beats(refcard, ctx)
    assert smaller_trump.beats(refcard, ctx)

def test_card_beats_bowers():
    """Test bowers against other trump, non-trump, and each other
    """
    refcard = find_card(jack, diamonds)
    refsuit = refcard.suit

    ctx = DummyContext()
    ctx.set_context(refsuit, refcard)

    testcard1 = find_card(ten, diamonds)
    testcard2 = find_card(queen, diamonds)
    testcard3 = find_card(king, diamonds)
    testcard4 = find_card(ace, diamonds)

    # test right bower
    assert refcard.beats(testcard1, ctx)
    assert refcard.beats(testcard2, ctx)
    assert refcard.beats(testcard3, ctx)
    assert refcard.beats(testcard4, ctx)

    # test left bower
    refcard2 = find_card(jack, hearts)
    assert refcard2.effsuit(ctx) == refsuit
    assert not refcard2.beats(refcard, ctx)

    assert refcard2.beats(testcard1, ctx)
    assert refcard2.beats(testcard2, ctx)
    assert refcard2.beats(testcard3, ctx)
    assert refcard2.beats(testcard4, ctx)

    # test bowers against non-trump
    testcard5 = find_card(ace, spades)
    assert testcard5.effsuit(ctx) != refsuit
    assert refcard.beats(testcard5, ctx)
    assert refcard2.beats(testcard5, ctx)
    assert not testcard5.beats(refcard, ctx)
    assert not testcard5.beats(refcard2, ctx)
