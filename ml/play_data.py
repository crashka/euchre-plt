#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import tempfile
from typing import TextIO
from itertools import chain
import re
from random import Random
import json

os.environ['EUCH_LOG_NAME'] = 'play_data'

from euchplt.utils import parse_argv
from euchplt.core import cfg, DataFile, ConfigError
from euchplt.card import get_deck
from euchplt.player import Player
from euchplt.deal import Deal, NUM_PLAYERS
from .strategy.play_traverse import PlayFeatures, PlayOutcome
from .strategy.play_traverse import CompOutcome, FMT_JSON

cfg.load('ml_data.yml')

########
# main #
########

DFLT_DEALS   = 1
TMP_TYPE     = '.dat'
FILE_TYPE    = '.tsv'
TMP_FILE_SZ  = 500  # number of decks
UPD_INTERVAL = 10
FIN_INTERVAL = 10000
MY_RANDOM    = Random()

def gen_run_id() -> str:
    """For now, just return a random hex string (inspired by git style, though
    not actually a hash of anything here)
    """
    return f"{MY_RANDOM.randrange(0x1000000):x}"

def get_file_name(model_name: str) -> str:
    """Convert to name to snake_case and add file type
    """
    return re.sub(r'\W+', '_', model_name).lower() + FILE_TYPE

def main() -> int:
    """Generate data for play model

    Usage: play_data.py <play_model> [deals=<ndeals>] [keep_tmp=<bool>]
    """
    args, kwargs = parse_argv(sys.argv[1:])
    if not args:
        raise RuntimeError("<play_model> not specified")
    name = args.pop(0)
    if len(args) > 0:
        args_str = ' '.join(str(a) for a in args)
        raise RuntimeError(f"Unexpected argument(s): {args_str}")
    ndeals = kwargs.get('deals') or DFLT_DEALS
    keep_tmp = kwargs.get('keep_tmp') or False

    play_models = cfg.config('play_models')
    if name not in play_models:
        raise RuntimeError(f"Play model '{name}' is not known")
    data_file = DataFile(get_file_name(name))  # this is the final output file

    # we use temp files to send raw outcomes to us from traversal procs (too
    # difficult to get queues, fifos, etc. to work); not pretty, but workable
    tmp_files = []
    tmp_file = None  # created as needed
    os.environ['PLAY_DATA_FORMAT'] = FMT_JSON

    player_name = play_models[name].get('data_player')
    if not player_name:
        raise ConfigError(f"'data_player' not specified for play model '{name}'")

    players = [Player(player_name) for _ in range(NUM_PLAYERS)]
    print(f"\rIterations: {0:2d}", end='')

    try:
        for i in range(1, ndeals + 1):
            if not tmp_file:
                _, tmp_file = tempfile.mkstemp(suffix=TMP_TYPE, text=True)
                tmp_files.append(tmp_file)
                # HACKY: see comment in bid_data.py
                os.environ['PLAY_DATA_FILE'] = tmp_file

            deck = get_deck()
            for j in range(4):
                os.environ['PLAY_DATA_POS'] = str(j)
                os.environ['PLAY_DATA_RUN_ID'] = gen_run_id()
                deal = Deal(players, deck)
                deal.deal_cards()
                deal.do_bidding()
                if deal.is_passed():
                    continue
                deal.play_cards()

            if i % TMP_FILE_SZ == 0:
                tmp_file = None

            if i % UPD_INTERVAL == 0:
                print(f"\rIterations: {i:2d}", end='')
    except:
        keep_tmp = True  # so we can debug
    print(f"\rIterations: {i:2d}")

    comp_features = {}
    comp_outcome  = {}
    cur_run_id    = None

    def fmt_out(*args) -> str:
        """Create tab-deliminted string of iterable inputs
        """
        # TODO (perhaps): use `csv` module, for stricter encoding (e.g. proper
        # quoting for values of type `str` that look numeric)???
        return '\t'.join(str(x) for x in chain(*args))

    def process_line(line: str, file: TextIO, decoded: dict = None) -> None:
        """Let caller pass in decoded data, if already parsed out
        """
        nonlocal comp_features, comp_outcome, cur_run_id
        decoded  = decoded or json.loads(line.rstrip())
        features = PlayFeatures._make(decoded['features'])
        my_key   = tuple(features.key.split(' '))

        if features.run_id != cur_run_id:
            if cur_run_id:
                finalize_run(cur_run_id, file)
            else:
                assert not comp_features and not comp_outcome
            cur_run_id = features.run_id

        if decoded['outcome']:
            outcome = PlayOutcome._make(decoded['outcome'])
            for i in range(1, len(my_key)):
                int_key = my_key[:i]
                if int_key not in comp_outcome:
                    key_str = ' '.join(str(c) for c in int_key)
                    raise RuntimeError(f"key {key_str} not in comp_outcome")
                comp_outcome[int_key].add(outcome)
            print(fmt_out(list(features), list(outcome)), file=file)
        else:
            comp_features[my_key] = features
            comp_outcome[my_key] = CompOutcome()

    def finalize_run(run_id: str, file: TextIO) -> None:
        nonlocal comp_features, comp_outcome

        for i, item in enumerate(comp_outcome.items()):
            key, comp_data = item
            outcome = comp_data.finalize()
            features = comp_features.pop(key)
            assert features.run_id == run_id
            print(fmt_out(list(features), list(outcome)), file=file)

        if comp_features:
            keys_str = ', '.join(comp_features.keys())
            raise RuntimeError(f"{len(comp_features)} features with no outcome: {keys_str}")

        comp_features = {}
        comp_outcome  = {}

    ifin = 0
    new_file = not os.path.exists(data_file) or os.path.getsize(data_file) == 0
    print(f"\rPost-processing: {0:5d}", end='')
    with open(data_file, 'a') as fileout:
        for tmp_file in tmp_files:
            with open(tmp_file, 'r') as filein:
                line = filein.readline()
                decoded = json.loads(line.rstrip())
                # if the first line was encoded as a list (as opposed to a dict),
                # it is assumed to a be header record, which we will either write
                # to `fileout` or ignore, depending on whether we are appending to
                # existing data
                if isinstance(decoded, list):
                    if new_file:
                        print(fmt_out(decoded), file=fileout)
                        new_file = False
                else:
                    process_line(line, fileout, decoded)
                    ifin += 1

                for line in filein:
                    process_line(line, fileout)
                    ifin += 1
                    if ifin % FIN_INTERVAL == 0:
                        print(f"\rPost-processing: {ifin:5d}", end='')
                if cur_run_id:
                    finalize_run(cur_run_id, fileout)
                else:
                    assert not comp_features and not comp_outcome
    print(f"\rPost-processing: {ifin:5d}")

    for tmp_file in tmp_files:
        if not keep_tmp:
            os.unlink(tmp_file)
        else:
            print(f"tmp file: {tmp_file}", file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
