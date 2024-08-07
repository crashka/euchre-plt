#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import random
import os

from ..utils import parse_argv
from ..core import log, dbg_hand
from ..card import SUITS, get_deck, set_seed as set_card_seed
from ..euchre import Hand
from .smart import HandAnalysisSmart

def tune_strategy_smart(*args, **kwargs) -> int:
    """Run through a deck of cards evaluating the strength of each hand "dealt",
    iterating over the four suits as trump.  This is used for manual inspection
    to help tune the `HandAnalysisSmart` parameters and biddable thresholds.

    FUTURE: it would be cool to create an interactive utility whereby the human
    evaluates a number of hands based on biddability, as well as absolute and/or
    relative hand assessments, and a fitting algorithm determines the full set of
    parameters implied by the end-user input.
    """
    HAND_CARDS = 5
    card_seed  = kwargs.get('card_seed') or os.getpid()  # for get_deck() PRNG
    set_card_seed(card_seed)

    log.addHandler(dbg_hand)
    log.info(f"set_card_seed({card_seed})")

    deck = get_deck()
    while len(deck) >= HAND_CARDS:
        cards = deck[:HAND_CARDS]
        cards.sort(key=lambda c: c.sortkey)
        analysis = HandAnalysisSmart(Hand(cards))
        for suit in SUITS:
            _ = analysis.hand_strength(suit)
        del deck[:HAND_CARDS]

    return 0

########
# main #
########

def main() -> int:
    """Built-in driver to invoke various utility functions for the module

    Usage: strategy.py <func_name> [<arg> ...]

    Functions/usage:

    - tune_strategy_smart [card_seed=<int>]
    """
    if len(sys.argv) < 2:
        print(f"Utility function not specified", file=sys.stderr)
        return -1
    elif sys.argv[1] not in globals():
        print(f"Unknown utility function '{sys.argv[1]}'", file=sys.stderr)
        return -1

    util_func = globals()[sys.argv[1]]
    args, kwargs = parse_argv(sys.argv[2:])

    return util_func(*args, **kwargs)

if __name__ == '__main__':
    sys.exit(main())
