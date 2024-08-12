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
  - Convert to single-page app using ajax to update fields/info
"""

from typing import NamedTuple
from collections.abc import Hashable, Sequence, Callable
from enum import Enum
from numbers import Number
import os.path

from flask import Flask, request, render_template, abort

from .to_yaml import to_yaml
from euchplt.core import cfg
from euchplt.card import ALL_RANKS, Suit, Card, CARDS, Deck, get_card, get_deck
from euchplt.euchre import Hand, Bid, NULL_BID, PASS_BID, DealState
from euchplt.player import Player
from euchplt.deal import NUM_PLAYERS, DEALER_POS, Deal
from euchplt.strategy import Strategy, StrategySmart
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

class DealPhase(Enum):
    """Note that the order of the values here should match the indexes in the `bid_play`
    element in the template
    """
    BIDDING = "Bidding"
    PLAYING = "Playing"

    @classmethod
    def is_bidding(cls, phase: int) -> bool:
        return list(cls)[phase] is cls.BIDDING

    @classmethod
    def is_playing(cls, phase: int) -> bool:
        return list(cls)[phase] is cls.PLAYING

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
    all_strategies = cfg.config('strategies', safe=True)
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
    phase_chk:    list[str]
    player_pos:   int
    pos_chk:      list[str]
    # bidding context
    anly:         HandAnalysisSmart
    strgy:        Strategy
    coeff:        list[Number]
    hand:         Hand
    turn:         Card
    turn_lbl:     str
    bidding:      list[BidInfo]
    base_bidding: list[BidInfo]
    # playing context
    rulesets:     dict[str, list[Callable]]
    deck:         Deck
    deal:         DealState
    persist:      list[dict]
    bid_seq:      list[tuple[str, ...]]
    play_seq:     list[tuple[str, ...]]
    seq_hands:    list[Deck]
    trick_chk:    list[str]
    discard:      Card
    # const members added by `render_app()`
    title:        str
    strategies:   list[str]
    cards:        tuple[Card, ...]
    help_txt:     dict[str, str]
    ref_links:    dict[str, str]

# some random convenience shortcuts (and hacks)
StrgyComps = tuple[Strategy, HandAnalysisSmart, list[Number]]
NULL_COEFF = [''] * 5  # to simplify the template
NULL_CARD  = Card(-1, None, None, '', '', -1, -1)  # this is a hack!
NULL_HAND  = Hand([NULL_CARD] * 5)
PASSES     = [PASS_BID] * 8
NONES      = [None] * 10

MAX_RULESET = 7
DUMMY_RULESETS = {name: [None] * MAX_RULESET for name in StrategySmart.RULESETS}

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
    # is to use ``len(ALL_RANKS)`` as the offset multiplier (rather than just hardwiring
    # 10, say, which is what most normal people would do)
    return card.rank.idx + disp_suit_offset[card.suit.idx]

# monkeypatch display properties for `Suit`, `Card`, and `Bid` to help keep things cleaner
# in the template and/or to be CSS-friendly
setattr(Suit, 'disp', property(Suit.__str__))
setattr(Card, 'disp', property(card_disp))
setattr(Bid, 'disp', property(Bid.__str__))

CARDS_BY_SUIT = sorted(CARDS, key=disp_key)
RANKS = [r.tag for r in ALL_RANKS]

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
    deck     = None
    hand     = None
    turn     = None
    anly     = None
    strgy    = None
    coeff    = NULL_COEFF
    rulesets = DUMMY_RULESETS

    strategy = request.args.get('strategy')
    if strategy:
        deck = get_deck()
        hand, turn = get_hand(deck)
        strgy, anly, coeff = get_strgy_comps(strategy, hand)
        strat = Strategy.new(strategy)
        rulesets = strat.ruleset
    phase = int(request.args.get('phase') or 0)
    phase_chk = ['', '']
    phase_chk[phase] = " checked"

    context = {
        'strategy':     strategy,
        'phase_chk':    phase_chk,
        'player_pos':   0 if strategy else -1,
        'pos_chk':      [" checked"] + [''] * 3,
        'anly':         anly,
        'strgy':        strgy,
        'coeff':        coeff,
        'hand':         hand,
        'turn':         turn,
        'turn_lbl':     "Turn card",
        'bidding':      None,
        'base_bidding': None,
        'rulesets':     rulesets,
        'deck':         deck,
        'deal':         None,
        'persist':      None,
        'bid_seq':      None,
        'play_seq':     None,
        'seq_hands':    None,
        'trick_chk':    [" checked"] + [''] * 4,
        'discard':      None
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
    return compute(form, export=True, revert=False)

def evaluate(form: dict) -> str:
    """Compute bidding for selected position and deal context (i.e. hand and turn card),
    using current analysis and strategy parameters
    """
    return compute(form)

def new_hand(form: dict) -> str:
    """Generate new deck (including hand and turn card), then recompute using current
    strategy parameters
    """
    deck = get_deck()
    hand, turn = get_hand(deck)
    return compute(form, deck=deck, hand=hand, turn=turn)

def compute(form: dict, **kwargs) -> str:
    """Dispatch to the compute method for the specified phase
    """
    if not (strategy := form.get('strategy')):
        abort(400, "Strategy not selected")
    elif strategy not in get_strategies():
        abort(400, f"Invalid strategy ({strategy}) specified")
    kwargs['strategy'] = strategy

    phase = int(form.get('phase') or 0)
    phase_chk = ['', '']
    phase_chk[phase] = " checked"
    kwargs['phase_chk'] = phase_chk

    if not (player_pos := form.get('player_pos')):  # note that bool('0') == True
        abort(400, "Player position not selected")
    player_pos = int(player_pos)
    kwargs['player_pos'] = player_pos
    pos_chk = [''] * 4
    pos_chk[player_pos] = " checked"
    kwargs['pos_chk'] = pos_chk

    trick = int(form.get('trick') or 0)
    trick_chk = [''] * 5
    trick_chk[trick] = " checked"
    kwargs['trick_chk'] = trick_chk

    if DealPhase.is_bidding(phase):
        return compute_bidding(form, **kwargs)
    elif DealPhase.is_playing(phase):
        return compute_playing(form, **kwargs)
    else:
        abort(404, f"Invalid phase '{phase}'")

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
    context['ranks']      = RANKS
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

####################
# Bidding Routines #
####################

def compute_bidding(form: dict, **kwargs) -> str:
    """Compute the hand strength and determine bidding for the current strategy and deal
    context (i.e. hand and turn card)

    Will continue using the hand and turn card from ``form`` if not specified in
    ``kwargs``
    """
    strategy   = kwargs['strategy']
    phase_chk  = kwargs['phase_chk']
    player_pos = kwargs['player_pos']
    pos_chk    = kwargs['pos_chk']
    trick_chk  = kwargs['trick_chk']

    # REVISIT: we pass the previous deck through to the template, even though hand and
    # turn card may be unrelated by now (due to position and/or manual card changes)--
    # perhaps better just to ignore deck in bidding analysis!!!
    deck:   Deck = kwargs.get('deck')
    hand:   Hand = kwargs.get('hand')
    turn:   Card = kwargs.get('turn')
    revert: bool = bool(kwargs.get('revert', False))
    export: bool = bool(kwargs.get('export', False))
    assert not (revert and export)

    if not hand:
        cards = [get_card(form[f'hand_{n}']) for n in range(5)]
        hand = Hand(sorted(cards, key=disp_key))
        turn = get_card(form['turn_card'])
        if not all_distinct(cards + [turn]):
            abort(400, "Duplicated cards not allowed")

    strgy_config = get_strgy_config(form) if not revert else {}
    strgy, anly, coeff = get_strgy_comps(strategy, hand, **strgy_config)
    base_strgy, base_anly, _ = get_strgy_comps(strategy, hand)
    # TODO: it would be cool to do a diff of the parameters, etc. so we could
    # highlight the ones that have been modified, and show the associated changes
    # in hand strength values as well!!!

    if export:
        strat_name = new_strgy_fmt % (strategy)
        return render_export(strat_name, strgy_config)

    bidding = get_bidding(strgy, player_pos, hand, turn)
    base_bidding = get_bidding(base_strgy, player_pos, hand, turn)

    context = {
        'strategy':     strategy,
        'phase_chk':    phase_chk,
        'player_pos':   player_pos,
        'pos_chk':      pos_chk,
        'anly':         anly,
        'strgy':        strgy,
        'coeff':        coeff,
        'hand':         hand,
        'turn':         turn,
        'turn_lbl':     "Turn card",
        'bidding':      bidding,
        'base_bidding': base_bidding,
        'rulesets':     {},
        'deck':         deck,
        'deal':         None,
        'persist':      None,
        'bid_seq':      None,
        'play_seq':     None,
        'seq_hands':    None,
        'trick_chk':    trick_chk,
        'discard':      None
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

def get_hand(deck: Deck = None, pos: int = 0) -> tuple[Hand, Card]:
    """Return a new randomly generated hand (sorted for display) and turn card
    """
    deck  = deck or get_deck()
    cards = deck[pos:20:NUM_PLAYERS]
    turn  = deck[20]
    hand  = Hand(sorted(cards, key=disp_key))
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
    TURN_SCORE = 'turn_card_score**'
    coeff_list = coeff_names.copy()
    sub_strgths = persist.get('sub_strgths')
    assert sub_strgths
    turn_strength = persist.get('turn_strength') or (0.0, 0.0, 0.0)
    hand_strength = persist.get('strength') - turn_strength[0]
    turn_pct = turn_strength[0] / hand_strength * 100.0
    if turn_strength[0]:
        sub_strgths[TURN_SCORE] = turn_strength
        coeff_list += [TURN_SCORE]

    lines = []
    # note we are hard-wiring the precision for this output (`FLOAT_PREC` is more
    # about aligning form-filling data with input precision in the template)
    lines.append(f"Hand Strength: {hand_strength:.2f}")
    lines.append("")
    lines.append("Subscore [0.0-1.0] (and Coeff):")
    for coeff_key in coeff_list:
        comp_val, raw_val, coeff = sub_strgths[coeff_key]
        lines.append(f"  {coeff_key}:  {raw_val:.2f} ({coeff:d})")
    lines.append("")
    lines.append("Component Strength Val:")
    for coeff_key in coeff_list:
        comp_val, raw_val, coeff = sub_strgths[coeff_key]
        lines.append(f"  {coeff_key}:  {comp_val:.2f}")
    lines.append("")
    lines.append("Component Strength Pct:")
    for coeff_key in coeff_list:
        comp_val, raw_val, coeff = sub_strgths[coeff_key]
        comp_pct = comp_val / hand_strength * 100.0
        lines.append(f"  {coeff_key}:  {comp_pct:.1f}%")
    if turn_strength:
        lines.append("")
        lines.append("(** turn_card_score not counted\n" +
                     "in hand strength, only shown for\n" +
                     "reference)")

    return '\n'.join(lines)

####################
# Playing Routines #
####################

def compute_playing(form: dict, **kwargs) -> str:
    """
    """
    strategy   = kwargs['strategy']
    phase_chk  = kwargs['phase_chk']
    player_pos = kwargs['player_pos']
    pos_chk    = kwargs['pos_chk']
    trick_chk  = kwargs['trick_chk']

    deck:   Deck = kwargs.get('deck')
    revert: bool = bool(kwargs.get('revert', False))
    export: bool = bool(kwargs.get('export', False))
    assert not (revert and export)

    if not deck:
        deck = [get_card(form[f'deck_{n}']) for n in range(24)]

    # I think we can use a single shared strategy here, since there is no state or
    # individual parameter overrides
    strat = Strategy.new(strategy)

    cards = None
    player_names = ["West", "North", "East", "South"]
    players = [Player(player_names[i], strat) for i in range(4)]
    while True:
        deal = Deal(players, deck)
        deal.deal_cards()
        deal.do_bidding()
        if deal.is_passed():
            continue
        mycards = deal.hands[player_pos].copy_cards()
        deal.play_cards()
        break

    assert mycards
    hand = Hand(sorted(mycards, key=disp_key))

    bid_seq = []
    for pos, bid in enumerate(deal.bids):
        you = " (you)" if (pos % 4) == player_pos else ""
        alone = " alone" if bid.alone else ""
        if bid is NULL_BID or (bid.is_defend() and not alone):
            continue
        player = deal.players[pos % NUM_PLAYERS].name
        bid_seq.append((player, bid, you))

    play_seq = []
    seq_hands = []
    for idx, trick in enumerate(deal.tricks):
        trick_seq = []
        cards = deal.played_by_pos[player_pos].copy_cards()[idx:]
        cards.sort(key=lambda c: c.sortkey)
        seq_hands.append(Hand(cards))
        for play in trick.plays:
            pos = play[0]
            you = " (you)" if pos == player_pos else ""
            win = " (win)" if trick.winning_pos == pos else ""
            player = deal.players[pos].name
            play_log = deal.player_state[pos]['play_log'][idx]
            rule = f"{play_log['ruleset']}: {play_log['rule'].__name__}"
            analysis = f"{play_log['reason']} [{rule}]"
            trick_seq.append((player, play[1], you, win, analysis))
        play_seq.append(trick_seq)

    if not deal.discard:
        turn_lbl = "Turned down"
    elif deal.caller_pos != 3:
        turn_lbl = "Ordered up"
    else:
        turn_lbl = "Picked up"

    context = {
        'strategy':     strategy,
        'phase_chk':    phase_chk,
        'player_pos':   player_pos,
        'pos_chk':      pos_chk,
        'anly':         None,
        'strgy':        None,
        'coeff':        NULL_COEFF,
        'hand':         hand,
        'turn':         deal.turn_card,
        'turn_lbl':     turn_lbl,
        'bidding':      None,
        'base_bidding': None,
        'rulesets':     strat.ruleset,
        'deck':         deck,
        'player':       deal.players[player_pos],
        'deal':         deal.deal_state(player_pos),
        'persist':      deal.player_state,
        'bid_seq':      bid_seq,
        'play_seq':     play_seq,
        'seq_hands':    seq_hands,
        'trick_chk':    trick_chk,
        'discard':      deal.discard
    }
    return render_app(context)


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
