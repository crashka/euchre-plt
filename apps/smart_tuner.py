#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to evaluate bidding strategies for ``StrategySmart``; useful
for manually testing/tweaking the various parameters, coefficients, and thresholds.

To start the server (local usage only)::

  $ python -m apps.smart_tuner

or::

  $ flask --app apps.smart_tuner run [--debug]

Note that ``--app smart_tuner`` (no parent module) should be specified if running from the
``apps/`` subdirectory.

To run the application, open a browser window and navigate to ``localhost:5000``.  The
usage of the application should be pretty self-explanatory.

To Do list:

- Nits

  - Fix trailing spaces in export parameter yaml generation
  - Handle special characters in new strategy names/comments (is this needed?)
  - Don't clear out deal info (and hide bidding) when switching strategies

- Enhancements

  - Configure rulesets for play strategy
  - Highlight params/coeffs that have been changed from the base config
  - Show more of the underlying computation for hand strength (e.g. individual component
    scores before coefficient weighting)
  - Convert to single-page app using ajax to update fields/info
"""

from typing import NamedTuple
from collections.abc import Hashable, Sequence
from numbers import Number
import os.path
import json

from flask import Flask, request, render_template, abort

from .to_yaml import to_yaml
from euchplt.core import cfg
from euchplt.card import ALL_RANKS, Suit, Card, CARDS, get_card, get_deck
from euchplt.euchre import Hand, Bid, PASS_BID, DealState
from euchplt.deal import NUM_PLAYERS
from euchplt.strategy import Strategy
from euchplt.analysis import HandAnalysisSmart

#########
# Setup #
#########

app = Flask(__name__)

APP_NAME       = "Smart Tuner"
APP_TEMPLATE   = "smart_tuner.html"
EXP_NAME       = "Smart Tuner Export"
EXP_TEMPLATE   = "smart_tuner_exp.html"
MSG_TEMPLATE   = "smart_tuner_msg.html"

APP_DIR        = os.path.dirname(os.path.realpath(__file__))
CONFIG_DIR     = os.path.join(APP_DIR, 'resources')
CONFIG_FILE    = 'strategies.yml'
CONFIG_PATH    = os.path.join(CONFIG_DIR, CONFIG_FILE)

STRATEGY_PATH  = 'euchplt.strategy'
STRATEGY_CLASS = 'StrategySmart'
new_strgy_fmt  = "%s (modified)"
_strategies    = None  # see NOTE in `get_strategies()`

def get_strategies(get_all: bool = False) -> list[str]:
    """Get list of relevant strategies (i.e. based on ``StrategySmart``)--includes both
    package- and app-level configurations

    Note, the ``get_all`` flag was added as a hack for outside callers and doesn't affect
    internal usage (though forces the local config to get reloaded)
    """
    # NOTE: not pretty to use a global here, but okay for this use case (just a tool)
    global _strategies
    if _strategies and not get_all:
        return _strategies

    cfg.load(CONFIG_FILE, CONFIG_DIR, reload=True)
    all_strategies = cfg.config('strategies')
    if get_all:
        return [k for k, v in all_strategies.items() if v.get('base_class')]
    _strategies = [k for k, v in all_strategies.items()
                   if v.get('base_class') == STRATEGY_CLASS]
    return _strategies

def reset_strategies() -> None:
    """Force ``get_strategies()`` to do a reload on next call
    """
    global _strategies
    _strategies = None

class BidInfo(NamedTuple):
    """Encapsulated bidding information for each hand and bidding position
    """
    round:     int     # 0-1
    pos:       int     # 0-3 (dealer = 3)
    bid_pos:   int     # TEMP: for debugging!!! 0-7
    discard:   Card    # only for round 1, pos 3 (bid_pos 3)
    new_hand:  Hand    # only for round 1, pos 3 (bid_pos 3)
    eval_suit: Suit    # turn suit (round 1) or best suit (round 2)
    strength:  Number  # aggregate (hand + turn)
    details:   str     # sub-strength contributions
    margin:    Number
    bid:       Bid

class Context(NamedTuple):
    """Context members referenced by the Jinja template

    Note: we may not use this directly, but at least it serves as a reference
    """
    strategy:     str
    player_pos:   int
    anly:         HandAnalysisSmart
    strgy:        Strategy
    coeff:        list[Number]
    hand:         Hand
    turn:         Card
    bidding:      list[BidInfo]
    base_bidding: list[BidInfo]
    # const members added by `render_app()`
    title:        str
    strategies:   list[str]
    cards:        tuple[Card, ...]
    help_txt:     dict[str, str]
    ref_links:    dict[str, str]

# some random convenience shortcuts
StrgyComps = tuple[Strategy, HandAnalysisSmart, list[Number]]
NULL_CARD  = Card(-1, None, None, '', '', -1, -1)  # hacky
NULL_HAND  = Hand([NULL_CARD] * 5)
PASSES     = [PASS_BID] * 8
NONES      = [None] * 10

FLOAT_PREC = 2

ranks = len(ALL_RANKS)
disp_suit_offset = [ranks, 0, 2 * ranks, 3 * ranks]

def card_disp(card: Card) -> str:
    """Add a space between rank and suit in the string representation for the card so we
    can use CSS ``word-spacing`` in the template (alternate version of ``__str__``)
    """
    return "%s %s" % (card.rank.tag, card.suit.tag)

def disp_key(card: Card) -> int:
    """Return sort key to use for displaying hands (alternate suit colors)
    """
    # Note: it's kind of wrong to use ``rank.idx`` here, but our cheeky way of justifying
    # is using ``len(ALL_RANKS)`` as the offset multiplier (rather than just hardwiring
    # 10, say, which is what most normal people would do)
    return card.rank.idx + disp_suit_offset[card.suit.idx]

# monkeypatch display properties for `Suit`, `Card`, and `Bid` to help keep things cleaner
# in the template and/or to be CSS-friendly
setattr(Suit, 'disp', property(Suit.__str__))
setattr(Card, 'disp', property(card_disp))
setattr(Bid, 'disp', property(Bid.__str__))

CARDS_BY_SUIT = sorted(CARDS, key=disp_key)

def all_distinct(seq: Sequence[Hashable]) -> bool:
    """Return `True` if all elements of input sequence are distinct (implemented by adding
    to a set and counting the members)
    """
    seqset = set(seq)
    return len(seqset) == len(list(seq))

def leading_spaces(line: str) -> int:
    """Return count of leading spaces in specified string
    """
    return len(line) - len(line.lstrip(' '))

################
# Flask Routes #
################

SUBMIT_FUNCS = [
    'revert_params',
    'export_params',
    'new_hand',
    'evaluate'
]

@app.get("/")
def index():
    """Get the analysis and strategy parameters for the specified strategy (or an empty
    form if ``strategy`` is not specified in the request)
    """
    anly  = None
    strgy = None
    coeff = [''] * 5  # shortcut (okay, hack) to simplify the template
    hand  = None
    turn  = None

    strategy = request.args.get('strategy')
    if strategy:
        hand, turn = get_hand()
        strgy, anly, coeff = get_strgy_comps(strategy, hand)

    context = {
        'strategy':   strategy,
        'player_pos': 0 if strategy else -1,
        'anly':       anly,
        'strgy':      strgy,
        'coeff':      coeff,
        'hand':       hand,
        'turn':       turn,
        'bids':       None,
        'base_bids':  None
    }
    return render_app(context)

@app.post("/")
def submit():
    """Process submitted form, switch on ``submit_func``, which is validated against
    values in ``SUBMIT_FUNCS``
    """
    func = request.form['submit_func']
    if func not in SUBMIT_FUNCS:
        abort(404, f"Invalid submit func '{func}'")
    return globals()[func](request.form)

def revert_params(form: dict) -> str:
    """Revert all parameters back to values specified by the selected strategy
    """
    return compute(form, revert=True)

def export_params(form: dict) -> str:
    """Export the current analysis and strategy parameters to YAML suitable for creating
    an entry in ``strategies.yaml``

    Later, we may support automatically creating the new entry in the config file
    """
    return compute(form, export=True)

def evaluate(form: dict) -> str:
    """Compute bidding for selected position and deal context (i.e. hand and turn card),
    using current analysis and strategy parameters
    """
    return compute(form)

def new_hand(form: dict) -> str:
    """Generate new hand and turn card, then recompute bidding using current analysis and
    strategy parameters
    """
    hand, turn = get_hand()
    return compute(form, hand=hand, turn=turn)

@app.post("/export")
def save_strategy():
    """We are only appending to the config file (to not screw up any pre-existing manual
    editing), noting that duplicate entries are fine (latest one will win)
    """
    if (submit_val := request.form['submit_val']) != 'save':
        abort(404, f"Invalid submit val '{submit_val}'")
    new_strategy = request.form['new_strategy']
    comments     = request.form['comments']
    config_yaml  = request.form['config_yaml']
    # get rid of horrible CRs from stupid html/textarea spec
    config_yaml  = config_yaml.replace('\r', '')

    with open(CONFIG_PATH, 'a') as f:
        f.write(config_yaml + '\n')
    reset_strategies()

    context = {
        'title': "Export Complete",
        'msg':   f"New strategy \"{new_strategy}\" created"
    }
    return render_template(MSG_TEMPLATE, **context)

################
# App Routines #
################

def render_app(context: dict) -> str:
    """Common post-processing of context before rendering the main app page through Jinja
    """
    context['title']      = APP_NAME
    context['strategies'] = get_strategies()
    context['cards']      = CARDS_BY_SUIT
    context['help_txt']   = help_txt
    context['ref_links']  = ref_links
    return render_template(APP_TEMPLATE, **context)

def render_export(strat_name: str, config_data: dict) -> str:
    """Export of analysis and strategy parameters
    """
    data = {
        strat_name: {
            'comments':        '',
            'module_path':     STRATEGY_PATH,
            'base_class':      STRATEGY_CLASS,
            'strategy_params': config_data
        }
    }
    context = {
        'title':      EXP_NAME,
        'strat_name': strat_name,
        'data':       to_yaml(data, indent=2, offset=4, maxsize=12)
    }
    return render_template(EXP_TEMPLATE, **context)

def compute(form: dict, **kwargs) -> str:
    """Compute the hand strength and determine bidding for the current strategy and deal
    context (i.e. hand and turn card)

    Will continue using the hand and turn card from ``form`` if not specified in
    ``kwargs``
    """
    hand:   Hand = kwargs.get('hand')
    turn:   Card = kwargs.get('turn')
    revert: bool = bool(kwargs.get('revert', False))
    export: bool = bool(kwargs.get('export', False))
    do_bid: bool = bool(kwargs.get('do_bid', True))

    # set and validate `strategy`
    if not (strategy := form.get('strategy')):
        abort(400, "Strategy not selected")
    elif strategy not in get_strategies():
        abort(400, f"Invalid strategy ({strategy}) specified")

    if not (player_pos := form.get('player_pos')):  # note that bool('0') == True
        abort(400, "Player position not selected")
    pos = int(player_pos)

    if not hand:
        cards = [get_card(form[f'hand_{n}']) for n in range(5)]
        hand = Hand(sorted(cards, key=disp_key))
        turn = get_card(form['turn_card'])
        if not all_distinct(cards + [turn]):
            abort(400, "Duplicated cards not allowed")

    if export:
        revert = False
        do_bid = False

    strgy_config = get_strgy_config(form) if not revert else {}
    strgy, anly, coeff = get_strgy_comps(strategy, hand, **strgy_config)
    base_strgy, base_anly, _ = get_strgy_comps(strategy, hand)
    # TODO: it would be cool to do a diff of the parameters, etc. so we could
    # highlight the ones that have been modified, and show the associated changes
    # in hand strength values as well!!!

    if do_bid:
        bidding = get_bidding(strgy, pos, hand, turn)
        base_bidding = get_bidding(base_strgy, pos, hand, turn)
    elif export:
        strat_name = new_strgy_fmt % (strategy)
        return render_export(strat_name, strgy_config)

    context = {
        'strategy':     form['strategy'],
        'player_pos':   pos,
        'anly':         anly,
        'strgy':        strgy,
        'coeff':        coeff,
        'hand':         hand,
        'turn':         turn,
        'bidding':      bidding,
        'base_bidding': base_bidding
    }
    return render_app(context)

def get_strgy_comps(strgy_name: str, hand: Hand, **kwargs) -> StrgyComps:
    """Get strategy and analysis components for the specified hand

    Note: ``coeff`` list (last member of the output tuple) is returned as a convenience
    (doing it here to make sure it is only done in one place, since it is a little dicey
    right now)
    """
    strgy  = Strategy.new(strgy_name, **kwargs)
    anly  = HandAnalysisSmart(hand, **strgy.hand_analysis)
    coeff = [v for k, v in anly.scoring_coeff.items()]
    return (strgy, anly, coeff)

def get_strgy_config(form: dict) -> dict:
    """Extract StrategySmart configuration (with embedded SmartHandAnalysis params),
    return format is the same as config file YAML
    """
    trump_values     = [int(form[f'tv_{n}']) for n in range(8)]
    suit_values      = [int(form[f'sv_{n}']) for n in range(6)]
    num_trump_scores = [float(form[f'nts_{n}']) for n in range(6)]
    off_aces_scores  = [float(form[f'nas_{n}']) for n in range(4)]
    voids_scores     = [float(form[f'nvs_{n}']) for n in range(4)]
    coeff_values     = [int(form[f'coeff_{n}']) for n in range(5)]
    scoring_coeff    = dict(zip(coeff_names, coeff_values))
    hand_analysis    = {
        'trump_values'    : trump_values,
        'suit_values'     : suit_values,
        'num_trump_scores': num_trump_scores,
        'off_aces_scores' : off_aces_scores,
        'voids_scores'    : voids_scores,
        'scoring_coeff'   : scoring_coeff
    }

    turn_card_value  = [int(form[f'tcv_{n}']) for n in range(8)]
    turn_card_coeff  = [int(form[f'tcc_{n}']) for n in range(4)]
    bid_thresh       = [int(form[f'bt_{n}']) for n in range(8)]
    alone_margin     = [int(form[f'am_{n}']) for n in range(8)]
    def_alone_thresh = [int(form[f'dat_{n}']) for n in range(11)]
    strgy_config  = {
        'hand_analysis'   : hand_analysis,
        'turn_card_value' : turn_card_value,
        'turn_card_coeff' : turn_card_coeff,
        'bid_thresh'      : bid_thresh,
        'alone_margin'    : alone_margin,
        'def_alone_thresh': def_alone_thresh
    }

    return strgy_config

def get_hand() -> tuple[Hand, Card]:
    """Return a new randomly generated hand (sorted for display) and turn card
    """
    deck = get_deck()
    cards = deck[:5]
    turn = deck[20]
    hand = Hand(sorted(cards, key=disp_key))
    return hand, turn

def get_bidding(strgy: Strategy, pos: int, hand: Hand, turn: Card) -> list[BidInfo]:
    """Return list of ``BidInfo`` information for the specified seat position, one entry
    for each round of bidding
    """
    bidding = []

    for rnd in range(2):
        bid_pos  = rnd * NUM_PLAYERS + pos
        bids     = PASSES[:bid_pos]
        persist  = {}  # addl output values from `bid()` call
        new_hand = None
        details  = None

        # construct minimum functional faux deal state (only bidding fields, and
        # `persist`, needed)
        deal = DealState(pos, hand, turn, bids, *NONES, persist)
        bid = strgy.bid(deal)  # this call updates `persist`!

        if strength := persist.get('strength'):
            strength = round(strength, FLOAT_PREC)
        if margin := persist.get('thresh_margin'):
            margin = round(margin, FLOAT_PREC)
        if cards := persist.get('new_hand'):
            new_hand = sorted(cards, key=disp_key)
        if best_suit := persist.get('best_suit'):
            eval_suit = best_suit
        else:
            eval_suit = turn.suit

        bid_info = BidInfo(rnd,
                           pos,
                           bid_pos,
                           persist.get('discard'),
                           new_hand,
                           eval_suit,
                           strength,
                           get_details(persist),
                           margin,
                           bid)
        bidding.append(bid_info)

    return bidding

def get_details(persist: dict) -> str:
    """Extract component sub-strength and turn card strength info from the strategy
    persistence store, and generate explanatory detail text
    """
    coeff_list = coeff_names.copy()
    sub_strgths = persist.get('sub_strgths')
    assert sub_strgths
    turn_strength = persist.get('turn_strength') or 0.0
    hand_strength = persist.get('strength') - turn_strength
    turn_pct = turn_strength / hand_strength * 100.0
    if turn_strength:
        sub_strgths['turn_card_score**'] = turn_strength
        coeff_list += ['turn_card_score**']

    lines = []
    # note we are hard-wiring the precision for this output (`FLOAT_PREC` is more
    # about aligning form-filling data with input precision in the template)
    lines.append(f"Hand Strength: {hand_strength:.2f}")
    lines.append("")
    lines.append("Component Strength Val:")
    for coeff in coeff_list:
        comp_val = sub_strgths[coeff]
        lines.append(f"  {coeff}:  {comp_val:.2f}")
    lines.append("")
    lines.append("Component Strength Pct:")
    for coeff in coeff_list:
        comp_val = sub_strgths[coeff]
        comp_pct = comp_val / hand_strength * 100.0
        lines.append(f"  {coeff}:  {comp_pct:.1f}%")
    if turn_strength:
        lines.append("")
        lines.append("(** turn_card_score not counted\n" +
                     "in hand strength, only shown for\n" +
                     "reference)")

    return '\n'.join(lines)

#########################
# Content / Metacontent #
#########################

# this is a little hacky, but does ensure that the coefficient structures are
# aligned between `get_strgy_comps` and `get_strgy_config`
anly = HandAnalysisSmart(NULL_HAND)
coeff_names = [c for c in anly.scoring_coeff]
del anly

help_txt = {
    # strategy select
    'st_0': "from strategies.yml config file",
    # bidding table
    'bd_0': "bidding round (1-2)",
    'bd_1': "corresponds to bid_pos for Strategy (above)",
    'bd_2': "",
    'bd_3': "",
    'bd_4': "hover over individual strengths to get details",
    'bd_5': "",
    'bd_6': ("turn suit (rd 1) or strongest suit (rd 2) is shown\n" +
             "when passing"),
    # submit buttons
    'bt_0': "",
    'bt_1': "",
    'bt_2': ("Compute bidding for selected position and deal\n" +
             "context (i.e. hand and turn card), using current\n" +
             "analysis and strategy parameters"),
    'bt_3': ("Generate new hand and turn card, then recompute\n" +
             "bidding using current analysis and strategy\n" +
             "parameters")
}

euchplt_pfx = "https://crashka.github.io/euchre-plt/_build/html/euchplt.html#euchplt."

ref_links = {
    "HandAnalysisSmart": euchplt_pfx + "analysis.HandAnalysisSmart",
    "StrategySmart":     euchplt_pfx + "strategy.StrategySmart"
}

############
# __main__ #
############

if __name__ == "__main__":
    app.run(debug=True)
