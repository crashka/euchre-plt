#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import environ
import sys

environ['EUCH_LOG_NAME'] = 'ml_data'

from euchplt.core import cfg
from euchplt.card import get_deck
from euchplt.player import Player
from euchplt.deal import Deal, NUM_PLAYERS
from euchplt.strategy import StrategySmart
from .strategy.bid_traverse import StrategyBidTraverse

cfg.load('ml_data.yml')

########
# main #
########

def main() -> int:
    """Built-in driver to run through a simple/sample deal
    """
    ndeals = 1
    if len(sys.argv) > 1:
        ndeals = int(sys.argv[1])

    players = [Player(f"Player {i+1}", StrategyBidTraverse()) for i in range(NUM_PLAYERS)]

    for _ in range(ndeals):
        deck = get_deck()
        deal = Deal(players, deck)

        deal.deal_cards()
        deal.do_bidding()
        if deal.is_passed():
            deal.print()
            continue
        deal.play_cards()
        deal.print(verbose=1)

    return 0

if __name__ == '__main__':
    sys.exit(main())
