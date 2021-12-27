#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import environ
import sys
import re

environ['EUCH_LOG_NAME'] = 'ml_data'

from euchplt.core import cfg, DataFile, DEBUG
from euchplt.card import get_deck
from euchplt.player import Player
from euchplt.deal import Deal, NUM_PLAYERS
from euchplt.strategy import StrategySmart
from .strategy.bid_traverse import StrategyBidTraverse

cfg.load('ml_data.yml')

########
# main #
########

FILE_TYPE    = '.dat'
UPD_INTERVAL = 10

def get_file_name(model_name: str) -> str:
    return re.sub(r'\W+', '_', model_name).lower() + FILE_TYPE

def main() -> int:
    """Generate data for bid model

    Usage: bid_data.py <bid_model> [<ndeals>]
    """
    ndeals = 1

    if len(sys.argv) < 2:
        raise RuntimeError("<bid_model> not specified")
    name = sys.argv[1]
    if len(sys.argv) > 2:
        ndeals = int(sys.argv[2])

    bid_models = cfg.config('bid_models')
    if name not in bid_models:
        raise RuntimeError(f"Bid model '{name}' is not known")
    file_name = get_file_name(name)
    # REVISIT: this is pretty hacky, but no good way to pass this information
    # down to the strategy class right now (see the other end of the hack in
    # bid_traverse.py)--should really make this prettier at some point!!!
    environ['BID_DATA_FILE'] = DataFile(file_name)

    player_name = bid_models[name].get('data_player')
    if not player_name:
        raise ConfigError(f"'data_player' not specified for bid model '{name}'")

    players = [Player(player_name) for _ in range(NUM_PLAYERS)]
    print(f"\rIterations: {0:2d}", end='')

    for i in range(1, ndeals + 1):
        deck = get_deck()
        deal = Deal(players, deck)

        deal.deal_cards()
        deal.do_bidding()
        if deal.is_passed():
            continue
        deal.play_cards()
        if i % UPD_INTERVAL == 0:
            print(f"\rIterations: {i:2d}", end='')

    print(f"\rIterations: {i:2d}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
