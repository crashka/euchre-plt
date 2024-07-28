#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to evaluate bidding strategies for ``StrategySmart``; useful
for manually testing/tweaking the various parameters, coefficients, and thresholds

To Do list:

- Sort cards in hand for display
- Highlight params/coeffs that have been changed from the base config
- Convert to single-page app using ajax
"""

from typing import NamedTuple
from numbers import Number
import json

from flask import Flask, request, render_template, abort

from euchplt.core import cfg
from euchplt.card import ALL_RANKS, Suit, Card, CARDS, get_card, get_deck
from euchplt.euchre import Hand, Bid, PASS_BID, DealState
from euchplt.deal import NUM_PLAYERS
from euchplt.strategy import Strategy
from euchplt.analysis import HandAnalysisSmart

app = Flask(__name__)

APP_NAME     = "Smart Tuner"
APP_TEMPLATE = "smart_tuner.html"
BASE_CLASS   = "StrategySmart"

strategy_list = cfg.config('strategies')
strategies = [k for k, v in strategy_list.items()
              if v['base_class'] == BASE_CLASS]

# see REVISIT comment in `get_strg_comps()`
coeff_names = [
    'trump_score',
    'max_suit_score',
    'num_trump_score',
    'off_aces_score',
    'voids_score'
]

SUBMIT_FUNCS = [
    'new_hand',
    'evaluate'
]

FLOAT_PREC = 2

# some random convenience shortcuts
StrgComps = tuple[Strategy, HandAnalysisSmart, list[Number]]
NULL_CARD = Card(-1, None, None, '', '', -1, -1)  # hacky
NULL_HAND = Hand([NULL_CARD] * 5)
PASSES    = [PASS_BID] * 8
NONES     = [None] * 10

class Bidding(NamedTuple):
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
    title:      str
    strategy:   str
    strategies: list[str]
    player_pos: int
    anly:       HandAnalysisSmart
    strg:       Strategy
    coeff:      list[Number]
    hand:       Hand
    turn:       Card
    bids:       list[Bidding]
    base_bids:  list[Bidding]

def get_strg_comps(strg_name: str, hand: Hand, **kwargs) -> StrgComps:
    """Get strategy and analysis components for the specified hand

    Note: ``coeff`` list is returned as a convenience (doing it here to make sure it is
    only done in one place, since it is a little dicey right now)
    """
    strg = Strategy.new(strg_name, **kwargs)
    anly = HandAnalysisSmart(hand, **strg.hand_analysis)
    # REVISIT: this is a little tenuous, depends on consistent ordering between config,
    # `coeff_names` (above), and Python dict management!!!
    coeff = [v for k, v in anly.scoring_coeff.items()]
    return (strg, anly, coeff)

ranks = len(ALL_RANKS)
disp_suit_offset = [ranks, 0, 2 * ranks, 3 * ranks]

def disp_key(card: Card) -> int:
    """Return sort key to use for displaying hands (alternate suit colors)
    """
    # Note: it's kind of wrong to use ``rank.idx`` here, but our cheeky way of justifying
    # is using ``len(ALL_RANKS)`` as the offset multiplier (rather than just hardwiring
    # 10, say, which is what most normal people would do)
    return card.rank.idx + disp_suit_offset[card.suit.idx]

def get_hand() -> tuple[Hand, Card]:
    """Return a new randomly generated hand (sorted for display) and turn card
    """
    deck = get_deck()
    cards = deck[:5]
    turn = deck[20]
    hand = Hand(sorted(cards, key=disp_key))
    return hand, turn

# monkeypatch display properties for ``Bid`` and ``Suit`` to help keep things cleaner
# in the template
setattr(Suit, 'disp', property(Suit.__str__))
setattr(Bid, 'disp', property(Bid.__str__))

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
    return render_template("smart_tuner.html", **context)

@app.post("/")
def submit():
    """Process submitted form, switch on ``submit_func`` equals either ``new_hand`` or
    ``evaluate``
    """
    func = request.form['submit_func']
    if func not in SUBMIT_FUNCS:
        abort(404, f"Invalid submit func '{func}'")
    return globals()[func](request.form)

def new_hand(form: dict) -> str:
    """Generate a new hand, the call ``evaluate()`` (using all existing parameters values)
    """
    hand, turn = get_hand()
    return evaluate(form, hand, turn)

def evaluate(form: dict, hand: Hand = None, turn: Card = None) -> str:
    """Compute the hand strength and determine bidding for the current strategy and deal
    context

    Will continue using the hand and turn card from ``form`` if not passed in (e.g. new
    hand requested)
    """
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

    trump_values     = [int(form[f'tv_{n}']) for n in range(8)]
    suit_values      = [int(form[f'sv_{n}']) for n in range(6)]
    num_trump_scores = [float(form[f'nts_{n}']) for n in range(6)]
    off_aces_scores  = [float(form[f'nas_{n}']) for n in range(4)]
    voids_scores     = [float(form[f'nvs_{n}']) for n in range(4)]
    coeff_values     = [int(form[f'coeff_{n}']) for n in range(5)]
    # see REVISIT in `get_strg_comps()`!
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
    def_alone_thresh = [int(form[f'dat_{n}']) for n in range(8)]
    strg_config  = {
        'turn_card_value' : turn_card_value,
        'turn_card_coeff' : turn_card_coeff,
        'bid_thresh'      : bid_thresh,
        'alone_margin'    : alone_margin,
        'def_alone_thresh': def_alone_thresh,
        'hand_analysis'   : hand_analysis
    }

    strg, anly, coeff       = get_strg_comps(strategy, hand, **strg_config)
    base_strg, base_anly, _ = get_strg_comps(strategy, hand)
    # TODO: it would be cool to do a diff of the parameters, etc. so we could highlight
    # the ones that have been modified, and show the associated changes in hand strength
    # values as well!!!

    bids      = get_bidding(strg, pos, hand, turn)
    base_bids = get_bidding(base_strg, pos, hand, turn)

    context = {
        'title':      APP_NAME,
        'strategy':   form['strategy'],
        'strategies': strategies,
        'player_pos': pos,
        'anly':       anly,
        'strg':       strg,
        'coeff':      coeff,
        'hand':       hand,
        'turn':       turn,
        'bids':       bids,
        'base_bids':  base_bids
    }
    return render_template(APP_TEMPLATE, **context)

def get_bidding(strg: Strategy, pos: int, hand: Hand, turn: Card) -> list[Bidding]:
    """Return list of ``Bidding`` information, one element for each bid position
    """
    ret = []

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
        if sub_strgths := persist.get('sub_strgths'):
            details = json.dumps(sub_strgths, indent=2)

        ret.append(Bidding(rnd,
                           pos,
                           bid_pos,
                           persist.get('discard'),
                           new_hand,
                           eval_suit,
                           strength,
                           details,
                           margin,
                           bid))
        pass  # for debugging

    return ret

if __name__ == "__main__":
    app.run(debug=True)
