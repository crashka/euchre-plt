# -*- coding: utf-8 -*-

import pytest

from euchplt.core import LogicError
from euchplt.card import ace, king, queen, jack, ten, nine, right, left
from euchplt.card import clubs, diamonds, hearts, spades, find_card, find_bower
from euchplt.euchre import GameCtxMixin, Hand

class DummyContext(GameCtxMixin):
    pass

def test_hand_crud():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    card6 = find_card(ace,   hearts)
    hand = Hand([card1, card2, card3, card4, card5])

    assert len(hand) == 5
    assert card1 in hand
    assert card2 in hand
    assert card3 in hand
    assert card4 in hand
    assert card5 in hand
    assert card6 not in hand

    hand_copy = hand.copy()
    assert card1 in hand_copy
    assert card2 in hand_copy
    assert card3 in hand_copy
    assert card4 in hand_copy
    assert card5 in hand_copy
    assert card6 not in hand_copy
    
    hand.append_card(card6)
    assert len(hand) == 6
    assert len(hand_copy) == 5
    assert card6 in hand
    assert card6 not in hand_copy

    hand.remove_card(card2)
    assert len(hand) == 5
    assert len(hand_copy) == 5
    assert card2 not in hand
    assert card2 in hand_copy

def test_cards_by_suit():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])

    # test with trump = diamonds
    ctx = DummyContext()
    ctx.set_trump_suit(diamonds)
    right_bower = find_bower(right, ctx.trump_suit)
    left_bower = find_bower(left, ctx.trump_suit)
    by_suit = hand.cards_by_suit(ctx, use_bowers=True)
    assert len(by_suit[clubs]) == 1
    assert set(by_suit[clubs]) == {card3}
    assert len(by_suit[diamonds]) == 4
    assert set(by_suit[diamonds]) == {card1, card2, right_bower, left_bower}
    assert len(by_suit[hearts]) == 0
    assert len(by_suit[spades]) == 0

    # test with trump = hearts
    ctx = DummyContext()
    ctx.set_trump_suit(hearts)
    right_bower = find_bower(right, ctx.trump_suit)
    left_bower = find_bower(left, ctx.trump_suit)
    by_suit = hand.cards_by_suit(ctx, use_bowers=True)
    assert len(by_suit[clubs]) == 1
    assert set(by_suit[clubs]) == {card3}
    assert len(by_suit[diamonds]) == 2
    assert set(by_suit[diamonds]) == {card1, card2}
    assert len(by_suit[hearts]) == 2
    assert set(by_suit[hearts]) == {right_bower, left_bower}
    assert len(by_suit[spades]) == 0

    # test with trump = spades
    ctx = DummyContext()
    ctx.set_trump_suit(spades)
    by_suit = hand.cards_by_suit(ctx)
    assert len(by_suit[clubs]) == 1
    assert set(by_suit[clubs]) == {card3}
    assert len(by_suit[diamonds]) == 3
    assert set(by_suit[diamonds]) == {card1, card2, card4}
    assert len(by_suit[hearts]) == 1
    assert set(by_suit[hearts]) == {card5}
    assert len(by_suit[spades]) == 0

def test_can_play_lead_trump():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])
    trump_suit = diamonds
    lead_card = find_card(nine, diamonds)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)
    assert hand.can_play(card1, ctx)
    assert hand.can_play(card2, ctx)
    assert not hand.can_play(card3, ctx)
    assert hand.can_play(card4, ctx)
    assert hand.can_play(card5, ctx)

def test_can_play_lead_next():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])
    trump_suit = diamonds
    lead_card = find_card(nine, hearts)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)
    assert hand.can_play(card1, ctx)
    assert hand.can_play(card2, ctx)
    assert hand.can_play(card3, ctx)
    assert hand.can_play(card4, ctx)
    assert hand.can_play(card5, ctx)

def test_can_play_lead_off_suit():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])
    trump_suit = diamonds
    lead_card = find_card(nine, clubs)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)
    assert not hand.can_play(card1, ctx)
    assert not hand.can_play(card2, ctx)
    assert hand.can_play(card3, ctx)
    assert not hand.can_play(card4, ctx)
    assert not hand.can_play(card5, ctx)

def test_can_play_lead_void_suit():
    card1 = find_card(king,  diamonds)
    card2 = find_card(queen, diamonds)
    card3 = find_card(ten,   clubs)
    card4 = find_card(jack,  diamonds)
    card5 = find_card(jack,  hearts)
    hand = Hand([card1, card2, card3, card4, card5])
    trump_suit = diamonds
    lead_card = find_card(nine, spades)

    ctx = DummyContext()
    ctx.set_trump_suit(trump_suit)
    ctx.set_lead_card(lead_card)
    assert hand.can_play(card1, ctx)
    assert hand.can_play(card2, ctx)
    assert hand.can_play(card3, ctx)
    assert hand.can_play(card4, ctx)
    assert hand.can_play(card5, ctx)
