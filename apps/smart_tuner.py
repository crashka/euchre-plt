#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to evaluate bidding strategies for ``StrategySmart``; useful
for manually testing/tweaking the various parameters, coefficients, and thresholds

To Do list:

- Open parameter export in a separate window
- Highlight params/coeffs that have been changed from the base config
- Convert to single-page app using ajax
"""

from typing import NamedTuple
from numbers import Number
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

APP_NAME     = "Smart Tuner"
APP_TEMPLATE = "smart_tuner.html"
EXP_NAME     = "Smart Tuner Export"
EXP_TEMPLATE = "smart_tuner_exp.html"

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
    title:        str
    strategy:     str
    strategies:   list[str]
    player_pos:   int
    anly:         HandAnalysisSmart
    strg:         Strategy
    coeff:        list[Number]
    hand:         Hand
    turn:         Card
    bidding:      list[BidInfo]
    base_bidding: list[BidInfo]
    help_txt:     dict[str, str]

# some random convenience shortcuts
StrgComps = tuple[Strategy, HandAnalysisSmart, list[Number]]
NULL_CARD = Card(-1, None, None, '', '', -1, -1)  # hacky
NULL_HAND = Hand([NULL_CARD] * 5)
PASSES    = [PASS_BID] * 8
NONES     = [None] * 10

FLOAT_PREC = 2

ranks = len(ALL_RANKS)
disp_suit_offset = [ranks, 0, 2 * ranks, 3 * ranks]

def disp_key(card: Card) -> int:
    """Return sort key to use for displaying hands (alternate suit colors)
    """
    # Note: it's kind of wrong to use ``rank.idx`` here, but our cheeky way of justifying
    # is using ``len(ALL_RANKS)`` as the offset multiplier (rather than just hardwiring
    # 10, say, which is what most normal people would do)
    return card.rank.idx + disp_suit_offset[card.suit.idx]

# monkeypatch display properties for ``Bid`` and ``Suit`` to help keep things cleaner
# in the template
setattr(Suit, 'disp', property(Suit.__str__))
setattr(Bid, 'disp', property(Bid.__str__))

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
    strg  = None
    coeff = [''] * 5  # shortcut (okay, hack) to simplify the template
    hand  = NULL_HAND
    turn  = NULL_CARD

    strategy = request.args.get('strategy')
    if strategy:
        hand, turn = get_hand()
        strg, anly, coeff = get_strg_comps(strategy, hand)

    context = {
        'title':      APP_NAME,
        'strategy':   strategy,
        'strategies': strategies,
        'player_pos': 0 if strategy else -1,
        'anly':       anly,
        'strg':       strg,
        'coeff':      coeff,
        'hand':       hand,
        'turn':       turn,
        'bids':       None,
        'base_bids':  None
    }
    return render_app(context)

@app.post("/")
def submit():
    """Process submitted form, switch on ``submit_func`` equals either ``new_hand`` or
    ``evaluate``
    """
    func = request.form['submit_func']
    if func not in SUBMIT_FUNCS:
        abort(404, f"Invalid submit func '{func}'")
    return globals()[func](request.form)

def revert_params(form: dict) -> str:
    """
    """
    return compute(form, revert=True)

def export_params(form: dict) -> str:
    """Export of analysis and strategy parameters
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

################
# App Routines #
################

def render_app(context: dict) -> str:
    """Common post-processing of context before rendering the main app page through Jinja
    """
    context['help_txt'] = help_txt
    return render_template(APP_TEMPLATE, **context)

def render_export(data: dict) -> str:
    """Export of analysis and strategy parameters
    """
    context = {
        'title': EXP_NAME,
        'data':  to_yaml(data, indent=2, offset=6, maxsize=12)
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
        abort(500, "Strategy not selected")
    elif strategy not in strategies:
        abort(500, f"Invalid strategy ({strategy}) specified")

    if not (player_pos := form.get('player_pos')):  # note that bool('0') == True
        abort(500, "Player position not selected")
    pos = int(player_pos)

    if not hand:
        hand = Hand([get_card(form[f'hand_{n}']) for n in range(5)])
        turn = get_card(form['turn_card'])

    if export:
        revert = False
        do_bid = False

    strg_config = get_strg_config(form) if not revert else {}
    strg, anly, coeff = get_strg_comps(strategy, hand, **strg_config)
    base_strg, base_anly, _ = get_strg_comps(strategy, hand)
    # TODO: it would be cool to do a diff of the parameters, etc. so we could
    # highlight the ones that have been modified, and show the associated changes
    # in hand strength values as well!!!

    if do_bid:
        bidding = get_bidding(strg, pos, hand, turn)
        base_bidding = get_bidding(base_strg, pos, hand, turn)
    elif export:
        return render_export(strg_config)

    context = {
        'title':        APP_NAME,
        'strategy':     form['strategy'],
        'strategies':   strategies,
        'player_pos':   pos,
        'anly':         anly,
        'strg':         strg,
        'coeff':        coeff,
        'hand':         hand,
        'turn':         turn,
        'bidding':      bidding,
        'base_bidding': base_bidding
    }
    return render_app(context)

def get_strg_comps(strg_name: str, hand: Hand, **kwargs) -> StrgComps:
    """Get strategy and analysis components for the specified hand

    Note: ``coeff`` list is returned as a convenience (doing it here to make sure it is
    only done in one place, since it is a little dicey right now)
    """
    strg  = Strategy.new(strg_name, **kwargs)
    anly  = HandAnalysisSmart(hand, **strg.hand_analysis)
    coeff = [v for k, v in anly.scoring_coeff.items()]
    return (strg, anly, coeff)

def get_strg_config(form: dict) -> dict:
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
    strg_config  = {
        'hand_analysis'   : hand_analysis,
        'turn_card_value' : turn_card_value,
        'turn_card_coeff' : turn_card_coeff,
        'bid_thresh'      : bid_thresh,
        'alone_margin'    : alone_margin,
        'def_alone_thresh': def_alone_thresh
    }

    return strg_config

def get_hand() -> tuple[Hand, Card]:
    """Return a new randomly generated hand (sorted for display) and turn card
    """
    deck = get_deck()
    cards = deck[:5]
    turn = deck[20]
    hand = Hand(sorted(cards, key=disp_key))
    return hand, turn

def get_bidding(strg: Strategy, pos: int, hand: Hand, turn: Card) -> list[BidInfo]:
    """Return list of ``BidInfo`` information, one element for each bid position
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
        bid = strg.bid(deal)  # this call updates `persist`!

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
    persistence, and generate explanatory detail text
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

BASE_CLASS = 'StrategySmart'

strategy_list = cfg.config('strategies')
strategies = [k for k, v in strategy_list.items()
              if v['base_class'] == BASE_CLASS]

# this is a little hacky, but does ensure that the coefficient structures are
# aligned between `get_strg_comps` and `get_strg_config`
anly = HandAnalysisSmart(NULL_HAND)
coeff_names = [c for c in anly.scoring_coeff]
del anly

help_txt = {}
# bidding table
help_txt['bd_0'] = "bidding round (1-2)"
help_txt['bd_1'] = "corresponds to bid_pos for Strategy (above)"
help_txt['bd_2'] = ""
help_txt['bd_3'] = ""
help_txt['bd_4'] = "hover over individual strengths to get details"
help_txt['bd_5'] = ""
help_txt['bd_6'] = ("turn suit (rd 1) or strongest suit (rd 2) is shown\n" +
                    "when passing")
# submit buttons
help_txt['bt_0'] = ""
help_txt['bt_1'] = ""
help_txt['bt_2'] = ("Compute bidding for selected position and deal\n" +
                    "context (i.e. hand and turn card), using current\n" +
                    "analysis and strategy parameters")
help_txt['bt_3'] = ("Generate new hand and turn card, then recompute\n" +
                    "bidding using current analysis and strategy\n" +
                    "parameters")

############
# __main__ #
############

if __name__ == "__main__":
    app.run(debug=True)
