#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to evaluate bidding strategies for ``StrategySmart``; useful
for manually testing/tweaking the various parameters, coefficients, and thresholds
"""

from flask import Flask, request, render_template, abort

from euchplt.core import cfg
from euchplt.card import get_deck
from euchplt.strategy import Strategy
from euchplt.analysis import HandAnalysisSmart

app = Flask(__name__)

APP_NAME = "Smart Tuner"

APP_TEMPLATE = "smart_tuner.html"

VALID_FUNCS = [
    'new_hand',
    'evaluate'
]

_strat_list = cfg.config('strategies')
strategies = [k for k, v in _strat_list.items() if v['base_class'] == "StrategySmart"]

@app.get("/")
def index():
    """Return an empty form
    """
    context = {
        'title':      APP_NAME,
        'form':       None,
        'strategies': strategies,
        # hacks to simplify the template
        'coeff':      [''] * 5,
        'hand':       [''] * 5,
        'turn':       ''
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
    deck = get_deck()
    hand = deck[:5]
    turn_card = deck[5]

    if 'strategy' not in form:
        abort(500, "Strategy not selected")
    strat_name = form['strategy']
    assert strat_name
    strg = Strategy.new(strat_name)
    anly = HandAnalysisSmart(hand, **strg.hand_analysis)
    # REVISIT: this is a little tenuous, depends on consistent ordering!!!
    coeff = [v for k, v in anly.scoring_coeff.items()]

    context = {
        'title':      APP_NAME,
        'form':       form,
        'strategies': strategies,
        'anly':       anly,
        'strg':       strg,
        'coeff':      coeff,
        # FIX: need to do better than use "tag" to communicate card values!!!
        'hand':       [str(card) for card in hand],
        'turn':       str(turn_card)
    }

    return render_template(APP_TEMPLATE, **context)

if __name__ == "__main__":
    app.run(debug=True)
