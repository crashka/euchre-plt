#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import environ
import sys
import re

environ['EUCH_LOG_NAME'] = 'ml_data'

from euchplt.utils import parse_argv
from euchplt.core import cfg, DataFile, ConfigError
from euchplt.card import get_deck
from euchplt.player import Player
from euchplt.deal import Deal, NUM_PLAYERS

cfg.load('ml_data.yml')

########
# main #
########

DFLT_DEALS   = 1
FILE_TYPE    = '.dat'
UPD_INTERVAL = 10

def get_file_name(model_name: str) -> str:
    return re.sub(r'\W+', '_', model_name).lower() + FILE_TYPE

def main() -> int:
    """Generate data for play model

    Usage: play_data.py <play_model> [deals=<ndeals>]
    """
    args, kwargs = parse_argv(sys.argv[1:])
    if not args:
        raise RuntimeError("<play_model> not specified")
    name = args.pop(0)
    if len(args) > 0:
        args_str = ' '.join(str(a) for a in args)
        raise RuntimeError(f"Unexpected argument(s): {args_str}")
    ndeals = kwargs.get('deals') or DFLT_DEALS

    play_models = cfg.config('play_models')
    if name not in play_models:
        raise RuntimeError(f"Play model '{name}' is not known")
    file_name = get_file_name(name)
    # HACKY: see comment in bid_data.py
    environ['PLAY_DATA_FILE'] = DataFile(file_name)

    player_name = play_models[name].get('data_player')
    if not player_name:
        raise ConfigError(f"'data_player' not specified for play model '{name}'")

    players = [Player(player_name) for _ in range(NUM_PLAYERS)]
    print(f"\rIterations: {0:2d}", end='')

    environ['PLAY_DATA_POS'] = str(0)
    for i in range(1, ndeals + 1):
        deck = get_deck()
        deal = Deal(players, deck)

        deal.deal_cards()
        deal.do_bidding()
        if deal.is_passed():
            continue
        deal.play_cards()
        deal.print(verbose=1)
        if i % UPD_INTERVAL == 0:
            print(f"\rIterations: {i:2d}", end='')

    print(f"\rIterations: {i:2d}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
