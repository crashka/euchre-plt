#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re

os.environ['EUCH_LOG_NAME'] = 'bid_data'

from euchplt.core import cfg, DataFile, DEBUG
from euchplt.utils import parse_argv
from euchplt.card import get_deck
from euchplt.player import Player
from euchplt.deal import Deal, NUM_PLAYERS
from euchplt.strategy import StrategySmart
from .strategy.bid_traverse import StrategyBidTraverse

cfg.load('ml_data.yml')

########
# main #
########

DFLT_DEALS   = 1
FILE_TYPE    = '.tsv'
UPD_INTERVAL = 10

def get_file_name(model_name: str) -> str:
    """Convert the name to snake_case and add file type
    """
    return re.sub(r'\W+', '_', model_name).lower() + FILE_TYPE

def main() -> int:
    """Generate data for bid model

    Usage: bid_data.py <bid_model> [deals=<ndeals>]
    """
    args, kwargs = parse_argv(sys.argv[1:])
    if not args:
        raise RuntimeError("<bid_model> not specified")
    name = args.pop(0)
    if len(args) > 0:
        args_str = ' '.join(str(a) for a in args)
        raise RuntimeError(f"Unexpected argument(s): {args_str}")
    ndeals = kwargs.get('deals') or DFLT_DEALS

    bid_models = cfg.config('bid_models')
    if name not in bid_models:
        raise RuntimeError(f"Bid model '{name}' is not known")
    file_name = get_file_name(name)
    # REVISIT: this is pretty hacky, but no good way to pass this information
    # down to the strategy class right now (see the other end of the hack in
    # bid_traverse.py)--should really make this prettier at some point!!!
    os.environ['BID_DATA_FILE'] = DataFile(file_name, add_ts=True)

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
