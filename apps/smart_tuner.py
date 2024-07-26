#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to evaluate bidding strategies for ``StrategySmart``; useful
for manually testing/tweaking the various parameters, coefficients, and thresholds
"""

from typing import NamedTuple
from numbers import Number

from flask import Flask, request, render_template, abort

from euchplt.core import cfg
from euchplt.card import Card, get_deck
from euchplt.euchre import Hand
from euchplt.strategy import Strategy
from euchplt.analysis import HandAnalysisSmart

app = Flask(__name__)

APP_NAME     = "Smart Tuner"
APP_TEMPLATE = "smart_tuner.html"
BASE_CLASS   = "StrategySmart"

VALID_FUNCS  = [
    'new_hand',
    'evaluate'
]

strategy_list = cfg.config('strategies')
strategies    = [k for k, v in strategy_list.items()
                 if v['base_class'] == BASE_CLASS]

StratParams   = tuple[Strategy, HandAnalysisSmart, list[Number]]
NULL_CARD     = Card(-1, None, None, '', '', -1, -1)  # hacky
NULL_HAND     = Hand([NULL_CARD] * 5)

coeff_names   = [
    'trump_score',
    'max_suit_score',
    'num_trump_score',
    'off_aces_score',
    'voids_score'
]

class Context(NamedTuple):
    """Context members referenced by the Jinja template

    Note: we may not use this directly, but at least it serves as a reference
    """
    title:      str
    strategy:   str
    strategies: list[str]
    anly:       HandAnalysisSmart
    strg:       Strategy
    coeff:      list[Number]
    base_anly:  HandAnalysisSmart
    base_strg:  Strategy
    hand:       Hand
    turn:       Card

def get_strat_comps(strat_name: str, hand: Hand, **kwargs) -> StratParams:
    """Get strategy and analysis components for the current hand

    Note: ``coeff`` is returned as a convenience (doing it here to make sure it is only
    done in one place, since it is a little dicey right now)
    """
    strg = Strategy.new(strat_name, **kwargs)
    anly = HandAnalysisSmart(hand, **strg.hand_analysis)
    # REVISIT: this is a little tenuous, depends on consistent ordering!!!
    coeff = [v for k, v in anly.scoring_coeff.items()]
    return (strg, anly, coeff)

@app.get("/")
def index():
    """Return an empty form
    """
    anly  = None
    strg  = None
    coeff = [''] * 5  # shortcut (okay, hack) to simplify the template
    hand  = NULL_HAND
    turn  = NULL_CARD

    strategy = request.args.get('strategy')
    if strategy:
        strg, anly, coeff = get_strat_comps(strategy, hand)

    context = {
        'title':      APP_NAME,
        'strategy':   strategy,
        'strategies': strategies,
        'anly':       anly,
        'strg':       strg,
        'coeff':      coeff,
        'base_anly':  None,
        'base_strg':  None,
        'hand':       hand,
        'turn':       turn
    }
    return render_template("smart_tuner.html", **context)

@app.post("/")
def submit():
    """Process submitted form, switch on ``submit_func`` equals either ``new_hand`` or
    ``evaluate``
    """
    func = request.form['submit_func']
    if func not in VALID_FUNCS:
        abort(404)
    return globals()[func](request.form)

def new_hand(form: dict) -> str:
    """Generate a new hand, the call ``evaluate()`` (using all existing parameters values)
    """
    return evaluate(form)

def evaluate(form: dict) -> str:
    """Compute the hand strength and determine bidding for the current strategy and deal
    context
    """
    if 'strategy' not in form:
        abort(500, "Strategy not selected")
    strategy = form['strategy']
    assert strategy

    deck = get_deck()
    hand = Hand(deck[:5])
    turn_card = deck[5]

    trump_values     = [form[f"tv_{n}"] for n in range(8)]
    suit_values      = [form[f"sv_{n}"] for n in range(6)]
    num_trump_scores = [form[f"nts_{n}"] for n in range(6)]
    off_aces_scores  = [form[f"nas_{n}"] for n in range(4)]
    voids_scores     = [form[f"nvs_{n}"] for n in range(4)]
    coeff_values     = [form[f"coeff_{n}"] for n in range(5)]
    # see REVISIT in `get_strat_comps()`!
    scoring_coeff    = dict(zip(coeff_names, coeff_values))
    hand_analysis    = {
        'trump_values'    : trump_values,
        'suit_values'     : suit_values,
        'num_trump_scores': num_trump_scores,
        'off_aces_scores' : off_aces_scores,
        'voids_scores'    : voids_scores,
        'scoring_coeff'   : scoring_coeff
    }

    turn_card_value  = [form[f"tcv_{n}"] for n in range(8)]
    turn_card_coeff  = [form[f"tcc_{n}"] for n in range(4)]
    bid_thresh       = [form[f"bt_{n}"] for n in range(8)]
    alone_margin     = [form[f"am_{n}"] for n in range(8)]
    def_alone_thresh = [form[f"dat_{n}"] for n in range(8)]
    strategy_config  = {
        'turn_card_value' : turn_card_value,
        'turn_card_coeff' : turn_card_coeff,
        'bid_thresh'      : bid_thresh,
        'alone_margin'    : alone_margin,
        'def_alone_thresh': def_alone_thresh,
        'hand_analysis'   : hand_analysis
    }

    strg, anly, coeff       = get_strat_comps(strategy, hand, **strategy_config)
    base_strg, base_anly, _ = get_strat_comps(strategy, hand)

    context = {
        'title':      APP_NAME,
        'strategy':   form['strategy'],
        'strategies': strategies,
        'anly':       anly,
        'strg':       strg,
        'coeff':      coeff,
        'base_anly':  base_anly,
        'base_strg':  base_strg,
        'hand':       hand,
        'turn':       turn_card
    }

    return render_template(APP_TEMPLATE, **context)

if __name__ == "__main__":
    app.run(debug=True)
