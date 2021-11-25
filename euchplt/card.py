#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import NamedTuple
import random

from .core import validate_basedata

##############
# Base Cards #
##############

"""
Suits
    C - 0
    D - 1
    H - 2
    S - 3

Companion suit
    suit ^ 0x3

Cards (rank and level)
    9  - 0-3   (1)
    10 - 4-7   (2)
    J  - 8-11  (3)
    Q  - 12-15 (4)
    K  - 16-19 (5)
    A  - 20-23 (6)

    L  - 24-27 (7)
    R  - 28-31 (8)

Suit
    card % 4

Rank
    card // 4
"""

################
# Rank / Bower #
################

class Rank(NamedTuple):
    idx:   int
    name:  str
    level: int
    tag:   str

    def __repr__(self):
        return str(self._asdict())

    def __str__(self):
        return self.tag

class Bower(Rank):
    pass

nine     = Rank(0, 'nine',  1, '9')
ten      = Rank(1, 'ten',   2, '10')
jack     = Rank(2, 'jack',  3, 'J')
queen    = Rank(3, 'queen', 4, 'Q')
king     = Rank(4, 'king',  5, 'K')
ace      = Rank(5, 'ace',   6, 'A')

left     = Bower(6, 'left',  7, 'L')
right    = Bower(7, 'right', 8, 'R')

RANKS    = (nine, ten, jack, queen, king, ace)
BOWERS   = (left, right)
ALLRANKS = RANKS + BOWERS

########
# Suit #
########

class Suit(NamedTuple):
    idx:  int
    name: str
    tag:  str

    def __repr__(self):
        return str(self._asdict())

    def __str__(self):
        return self.tag

clubs    = Suit(0, 'clubs',    '\u2663')
diamonds = Suit(1, 'diamonds', '\u2666')
hearts   = Suit(2, 'hearts',   '\u2665')
spades   = Suit(3, 'spades',   '\u2660')

SUITS    = (clubs, diamonds, hearts, spades)

########
# Card #
########

class Card(NamedTuple):
    """
    """
    idx:     int
    rank:    Rank
    suit:    Suit
    name:    str
    tag:     str
    level:   int
    sortkey: int

    def __repr__(self):
        return str(self._asdict())

    def __str__(self):
        return self.tag

card_list = []
for idx in range(0, len(SUITS) * len(RANKS)):
    rank    = RANKS[idx // len(SUITS)]
    suit    = SUITS[idx % len(SUITS)]
    name    = "%s of %s" % (rank.name.capitalize(), suit.name.capitalize())
    tag     = "%s%s" % (rank.tag, suit.tag)
    level   = rank.level
    sortkey = suit.idx * len(ALLRANKS) + rank.idx + 1

    card = Card(idx, rank, suit, name, tag, level, sortkey)
    card_list.append(card)

CARDS = tuple(card_list)
del card_list

def find_card(rank: Rank, suit: Suit) -> Card:
    return CARDS[rank.idx * len(SUITS) + suit.idx]

########
# Deck #
########

Deck = list[Card]

def get_deck() -> Deck:
    """Get a shuffled deck of cards.  This function uses the `random` module, but it is up to
    the caller as to whether `seed()` is called beforehand.  Later on, we can support various
    suffling techniques that mimic physical suffling of cards based on the collection of a
    previous set of tricks and buries.
    """
    deck = [c for c in random.sample(CARDS, k=len(CARDS))]
    return deck

##############
# validation #
##############

validate_basedata(RANKS)
validate_basedata(BOWERS, len(RANKS))
validate_basedata(SUITS)
validate_basedata(CARDS)
