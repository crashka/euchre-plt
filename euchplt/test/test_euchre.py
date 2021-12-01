# -*- coding: utf-8 -*-

import pytest

from euchplt.core import LogicError
from euchplt.card import SUITS, CARDS, ace, king, queen, jack, ten, left, right
from euchplt.card import clubs, diamonds, hearts, spades, find_card, find_bower
from euchplt.euchre import GameCtxMixin

class DummyContext(GameCtxMixin):
    pass

def test_game_context():
    mysuit = clubs
    mycard = find_card(king, diamonds)

    ctx = DummyContext()
    assert ctx.trump_suit is None
    assert ctx.lead_card is None
    ctx.set_trump_suit(mysuit)
    ctx.set_lead_card(mycard)
    assert ctx.trump_suit == mysuit
    assert ctx.lead_card == mycard
    # can't re-set properties, even to same value
    with pytest.raises(LogicError):
        ctx.set_trump_suit(mysuit)
    with pytest.raises(LogicError):
        ctx.set_lead_card(mycard)

def test_trump_lead_cmp():
    """Note, we're leading trump, but staying away from bowers in this test
    """
    trump_suit = diamonds
    next_suit  = trump_suit.next_suit()
    lead_card  = find_card(ten, trump_suit)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)

    # test within trump suit
    ref_card  = find_card(king, trump_suit)
    bigger_trump = find_card(ace, trump_suit)
    assert bigger_trump.beats(ref_card, ctx)
    smaller_trump = find_card(queen, trump_suit)
    assert not smaller_trump.beats(ref_card, ctx)

    # test against non-trump
    ref_card  = find_card(king, trump_suit)
    bigger_non_trump = find_card(ace, next_suit)
    assert not bigger_non_trump.beats(ref_card, ctx)
    smaller_non_trump = find_card(queen, next_suit)
    assert not smaller_non_trump.beats(ref_card, ctx)

    # test non-trump against trump
    ref_card = find_card(king, next_suit)
    assert ref_card.suit != trump_suit
    assert bigger_trump.beats(ref_card, ctx)
    assert smaller_trump.beats(ref_card, ctx)

def test_non_trump_lead_cmp():
    """Note, we're leading non-trump to test following of lead, but still staying
    away from bowers in this test
    """
    trump_suit = diamonds
    next_suit  = trump_suit.next_suit()
    lead_card  = find_card(ten, next_suit)
    lead_suit  = lead_card.suit
    off_suit   = SUITS[trump_suit.idx ^ 0x02]  # little bit of magic!!!
    assert off_suit != trump_suit
    assert off_suit != lead_suit

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)

    # test follow aginst trump
    ref_card  = find_card(king, lead_suit)
    bigger_trump = find_card(ace, trump_suit)
    assert bigger_trump.beats(ref_card, ctx)
    smaller_trump = find_card(queen, trump_suit)
    assert smaller_trump.beats(ref_card, ctx)

    # test follow against follow
    ref_card  = find_card(king, lead_suit)
    bigger_follow = find_card(ace, lead_suit)
    assert bigger_follow.beats(ref_card, ctx)
    smaller_follow = find_card(queen, lead_suit)
    assert not smaller_follow.beats(ref_card, ctx)

    # test follow against throw-off
    ref_card  = find_card(king, lead_suit)
    bigger_throw_off = find_card(ace, off_suit)
    assert not bigger_throw_off.beats(ref_card, ctx)
    smaller_throw_off = find_card(queen, off_suit)
    assert not smaller_throw_off.beats(ref_card, ctx)

    # test throw-off against trump
    ref_card = find_card(king, off_suit)
    bigger_trump = find_card(ace, trump_suit)
    assert bigger_trump.beats(ref_card, ctx)
    smaller_trump = find_card(queen, trump_suit)
    assert smaller_trump.beats(ref_card, ctx)

    # test throw-off against follow
    ref_card = find_card(king, off_suit)
    bigger_trump = find_card(ace, trump_suit)
    assert bigger_trump.beats(ref_card, ctx)
    smaller_trump = find_card(queen, trump_suit)
    assert smaller_trump.beats(ref_card, ctx)

    # test throw-off against throw-off
    ref_card = find_card(king, off_suit)
    bigger_throw_off = find_card(ace, off_suit)
    with pytest.raises(LogicError):
        _ = bigger_throw_off.beats(ref_card, ctx)
    smaller_throw_off = find_card(queen, off_suit)
    with pytest.raises(LogicError):
        _ = smaller_throw_off.beats(ref_card, ctx)

def test_bowers_cmp():
    """Test bowers against other trump, non-trump, and each other
    """
    trump_suit      = diamonds
    next_suit       = trump_suit.next_suit()
    lead_card       = find_card(ten, trump_suit)
    right_bower     = find_bower(right, trump_suit)
    left_bower      = find_bower(left, trump_suit)
    right_bower_alt = find_card(jack, trump_suit)
    left_bower_alt  = find_card(jack, next_suit)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)

    # other trumps
    testcard1 = find_card(queen, trump_suit)
    testcard2 = find_card(king, trump_suit)
    testcard3 = find_card(ace, trump_suit)
    # non-trumps
    testcard4 = find_card(queen, next_suit)
    testcard5 = find_card(king, next_suit)
    testcard6 = find_card(ace, next_suit)

    # test right bower
    assert right_bower.beats(testcard1, ctx)
    assert right_bower.beats(testcard2, ctx)
    assert right_bower.beats(testcard3, ctx)
    assert right_bower.beats(testcard4, ctx)
    assert right_bower.beats(testcard5, ctx)
    assert right_bower.beats(testcard6, ctx)
    assert right_bower.beats(left_bower, ctx)
    assert right_bower.beats(left_bower_alt, ctx)
    assert right_bower_alt.beats(testcard1, ctx)
    assert right_bower_alt.beats(testcard2, ctx)
    assert right_bower_alt.beats(testcard3, ctx)
    assert right_bower_alt.beats(testcard4, ctx)
    assert right_bower_alt.beats(testcard5, ctx)
    assert right_bower_alt.beats(testcard6, ctx)
    assert right_bower_alt.beats(left_bower, ctx)
    assert right_bower_alt.beats(left_bower_alt, ctx)

    # test left bower
    assert left_bower.beats(testcard1, ctx)
    assert left_bower.beats(testcard2, ctx)
    assert left_bower.beats(testcard3, ctx)
    assert left_bower.beats(testcard4, ctx)
    assert left_bower.beats(testcard5, ctx)
    assert left_bower.beats(testcard6, ctx)
    assert not left_bower.beats(right_bower, ctx)
    assert not left_bower.beats(right_bower_alt, ctx)
    assert left_bower_alt.beats(testcard1, ctx)
    assert left_bower_alt.beats(testcard2, ctx)
    assert left_bower_alt.beats(testcard3, ctx)
    assert left_bower_alt.beats(testcard4, ctx)
    assert left_bower_alt.beats(testcard5, ctx)
    assert left_bower_alt.beats(testcard6, ctx)
    assert not left_bower_alt.beats(right_bower, ctx)
    assert not left_bower_alt.beats(right_bower_alt, ctx)

def test_bowers_cmp2():
    """Test bowers against other trump, non-trump, and each other, same as
    previous test, but non-trump lead
    """
    trump_suit      = diamonds
    next_suit       = trump_suit.next_suit()
    lead_card       = find_card(ten, next_suit)
    right_bower     = find_bower(right, trump_suit)
    left_bower      = find_bower(left, trump_suit)
    right_bower_alt = find_card(jack, trump_suit)
    left_bower_alt  = find_card(jack, next_suit)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)

    # other trumps
    testcard1 = find_card(queen, trump_suit)
    testcard2 = find_card(king, trump_suit)
    testcard3 = find_card(ace, trump_suit)
    # non-trumps
    testcard4 = find_card(queen, next_suit)
    testcard5 = find_card(king, next_suit)
    testcard6 = find_card(ace, next_suit)

    # test right bower
    assert right_bower.beats(testcard1, ctx)
    assert right_bower.beats(testcard2, ctx)
    assert right_bower.beats(testcard3, ctx)
    assert right_bower.beats(testcard4, ctx)
    assert right_bower.beats(testcard5, ctx)
    assert right_bower.beats(testcard6, ctx)
    assert right_bower.beats(left_bower, ctx)
    assert right_bower.beats(left_bower_alt, ctx)
    assert right_bower_alt.beats(testcard1, ctx)
    assert right_bower_alt.beats(testcard2, ctx)
    assert right_bower_alt.beats(testcard3, ctx)
    assert right_bower_alt.beats(testcard4, ctx)
    assert right_bower_alt.beats(testcard5, ctx)
    assert right_bower_alt.beats(testcard6, ctx)
    assert right_bower_alt.beats(left_bower, ctx)
    assert right_bower_alt.beats(left_bower_alt, ctx)

    # test left bower
    assert left_bower.beats(testcard1, ctx)
    assert left_bower.beats(testcard2, ctx)
    assert left_bower.beats(testcard3, ctx)
    assert left_bower.beats(testcard4, ctx)
    assert left_bower.beats(testcard5, ctx)
    assert left_bower.beats(testcard6, ctx)
    assert not left_bower.beats(right_bower, ctx)
    assert not left_bower.beats(right_bower_alt, ctx)
    assert left_bower_alt.beats(testcard1, ctx)
    assert left_bower_alt.beats(testcard2, ctx)
    assert left_bower_alt.beats(testcard3, ctx)
    assert left_bower_alt.beats(testcard4, ctx)
    assert left_bower_alt.beats(testcard5, ctx)
    assert left_bower_alt.beats(testcard6, ctx)
    assert not left_bower_alt.beats(right_bower, ctx)
    assert not left_bower_alt.beats(right_bower_alt, ctx)
