#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple form-based web app to run tournaments.

To start the server (local usage only)::

  $ python -m apps.tournament_runner

or::

  $ flask --app apps.tournament_runner run [--debug]

Note that ``--app tournament_runner`` (no parent module) should be specified if running
from the ``apps/`` subdirectory.

To run the application, open a browser window and navigate to ``localhost:5000``.  The
usage of the application should be pretty self-explanatory.

To Do list:

"""

from numbers import Number
from collections.abc import Iterator
import os.path
from time import time
import shelve

from flask import Flask, session, request, render_template, abort

from euchplt.core import cfg
from euchplt.tournament import Tournament, LB_PRINT_STATS

#########
# Setup #
#########

app = Flask(__name__)
app.config.from_prefixed_env('EUCH')

APP_NAME      = "Tournament Runner"
APP_TEMPLATE  = "tournament_runner.html"
DASH_NAME     = "Tournament Dashboard"
DASH_TEMPLATE = "tournament_dash.html"

APP_DIR       = os.path.dirname(os.path.realpath(__file__))
RESOURCES_DIR = os.path.join(APP_DIR, 'resources')
CONFIG_FILE   = 'tournaments.yml'
CONFIG_PATH   = os.path.join(RESOURCES_DIR, CONFIG_FILE)

TOURN_CLASSES = {'RoundRobin', 'ChallengeLadder'}

_tournaments  = None  # see NOTE in `get_tournaments()`

def get_tournaments() -> list[str]:
    """Get list of pre-configured tournaments--includes both package- and app-level
    entries
    """
    # NOTE: not pretty to use a global here, but okay for this use case (just a tool)
    global _tournaments
    if _tournaments:
        return _tournaments

    cfg.load(CONFIG_FILE, RESOURCES_DIR, reload=True)
    all_tournaments = cfg.config('tournaments')
    _tournaments = [k for k, v in all_tournaments.items()
                    if v.get('tourn_class') in TOURN_CLASSES]
    return _tournaments

def reset_tournaments() -> None:
    """Force ``get_tournaments()`` to do a reload on next call
    """
    global _tournaments
    _tournaments = None

def gen_tourn_id(tourn: Tournament) -> str:
    """Generate a hex-looking ID for the tournament, based on the python ``id()`` of the
    ``Tournament`` instance and current timestamp
    """
    return hex(hash(tourn) ^ hash(time()))[2:]

def get_db_file(tourn_id: str) -> str:
    """Get the ``shelve`` "db" file for the specified tournament (by ID)
    """
    return f"tourn-{tourn_id}.db"

def save_tournament(tourn_id: str, tourn: Tournament) -> None:
    """Persist the tournament information (including stats)
    """
    db_file = get_db_file(tourn_id)
    db_path = os.path.join(RESOURCES_DIR, db_file)
    with shelve.open(db_path, flag='c') as db:
        db['tourn'] = tourn

def retrieve_tournament(tourn_id: str) -> Tournament:
    """Retrieve the tournament information (including stats)
    """
    db_file = get_db_file(tourn_id)
    db_path = os.path.join(RESOURCES_DIR, db_file)
    with shelve.open(db_path) as db:
        # ATTN: can probably do this without the comprehension loop!!!
        data = {k: v for k, v in db.items()}
    return data.get('tourn')

FLOAT_PREC = 1

def round_val(val: Number) -> Number:
    """Provide the appropriate level of rounding for the leaderboard or stat value (leave
    as a number)
    """
    if isinstance(val, float):
        return round(val, FLOAT_PREC)
    return val

################
# Flask Routes #
################

SUBMIT_FUNCS = [
    'run_tourn',
    'next_pass'
]

INIT_TIMER = "0:00"
INIT_START = 0  # to make parseInt() work

@app.get("/")
def index():
    """Get the configuration info for specified tournament (or an empty form if
    ``tourn_name`` is not specified in the request)
    """
    tourn_fmt   = None
    match_games = None
    passes      = None
    reset_elo   = False

    tourn_name = request.args.get('tourn_name')
    if tourn_name:
        tourn = Tournament.new(tourn_name)
        tourn_fmt   = tourn.__class__.__name__
        match_games = tourn.match_games
        passes      = tourn.passes
        reset_elo   = tourn.reset_elo

    context = {
        'tourn_name':  tourn_name,
        'tourn_fmt':   tourn_fmt,
        'match_games': match_games,
        'passes':      passes,
        'reset_elo':   reset_elo
    }
    return render_app(context)

@app.post("/tournament")
def submit():
    """Process submitted form, switch on ``submit_func``, which is validated against
    values in ``SUBMIT_FUNCS``
    """
    func = request.form['submit_func']
    if func not in SUBMIT_FUNCS:
        abort(404, f"Invalid submit func '{func}'")
    return globals()[func](request.form)

def run_tourn(form: dict) -> str:
    """Compute bidding for selected position and deal context (i.e. hand and turn card),
    using current analysis and strategy parameters
    """
    tourn_name = form.get('tourn_name')
    # TODO: get override parameters from form, used to instantiate tournament!!!
    tourn = Tournament.new(tourn_name)
    tourn_id = gen_tourn_id(tourn)
    save_tournament(tourn_id, tourn)
    session['tourn_id'] = tourn_id

    run_msg = "Starting tournament..."
    context = {
        'tourn':      tourn,
        'lb_col_cls': None,
        'lb_td_cls':  None,
        'lb_header':  None,
        'lb_data':    None,
        'timer':      INIT_TIMER,
        'start':      INIT_START,
        'winner':     None,
        'msg':        run_msg
    }
    return render_dashboard(context)

col_map = {
    str:   "col_txt",
    int:   "col_num",
    float: "col_dec"
}

td_map = {
    str:   "td_txt",
    int:   "td_num",
    float: "td_dec"
}

def next_pass(form: dict) -> str:
    """
    """
    winner = None
    tourn_id = session['tourn_id']
    tourn = retrieve_tournament(tourn_id)
    # REVISIT: clunky use of local `pass_num`, see note in `RoundRobin.run_pass()`!!!
    pass_num = tourn.pass_num + 1
    assert pass_num < tourn.passes

    lb = tourn.run_pass(pass_num)
    save_tournament(tourn_id, tourn)
    if pass_num + 1 < tourn.passes:
        assert pass_num + 1 == len(tourn.leaderboards)
        pass_msg = f"Completed pass {pass_num + 1} of {tourn.passes}"
    else:
        plural = "s" if len(tourn.winner) > 1 else ""
        winner = ', '.join(tourn.winner)
        pass_msg = f"Tournament \"{tourn.name}\" complete, winner{plural}: {winner}"

    stats_row = next(iter(lb.values()))
    # note that all of the following include team info in the [0] position
    lb_col_cls = ["col_lbl"] + [col_map[type(v)] for k, v in stats_row.items()
                                if k in LB_PRINT_STATS]
    lb_td_cls  = ["td_lbl"]  + [td_map[type(v)] for k, v in stats_row.items()
                                if k in LB_PRINT_STATS]
    lb_header  = ["Team"]    + [str(k) for k in stats_row.keys()
                                if k in LB_PRINT_STATS]
    lb_data   = []
    for team, stats in lb.items():
        row = [team] + [round_val(v) for k, v in stats.items()
                        if k in LB_PRINT_STATS]
        lb_data.append(row)

    # this won't be perfectly correlated with client side timer, so sometimes
    # glitchy, but as close as we can get
    elapsed = int(time()) - int(form.get('start')) // 1000
    timer = f"{elapsed // 60}:{elapsed % 60:02d}"

    context = {
        'tourn':      tourn,
        'lb_col_cls': lb_col_cls,
        'lb_td_cls':  lb_td_cls,
        'lb_header':  lb_header,
        'lb_data':    lb_data,
        'timer':      timer,
        'start':      form.get('start'),
        'winner':     winner,
        'msg':        pass_msg
    }

    return render_dashboard(context)

################
# App Routines #
################

def render_app(context: dict) -> str:
    """Common post-processing of context before rendering the main app page through Jinja
    """
    context['title']      = APP_NAME
    context['tourn_list'] = get_tournaments()
    context['help_txt']   = help_txt
    context['ref_links']  = ref_links
    return render_template(APP_TEMPLATE, **context)

def render_dashboard(context: dict) -> str:
    """Render the dashboard, from which the tournament will be run and tracked (assuming
    we can successfully serialize it!)
    """
    context['title'] = DASH_NAME + f" - {context['tourn'].name}"
    return render_template(DASH_TEMPLATE, **context)

#########################
# Content / Metacontent #
#########################

help_txt = {
    # tournament select
    'tn_0': "from tournaments.yml config file",

    # submit buttons
    'bt_0': "Start tournament and track using the dashboard",
}

euchplt_pfx = "https://crashka.github.io/euchre-plt/_build/html/euchplt.html#"

ref_links = {
    "Tournament": euchplt_pfx + "module-euchplt.tournament"
}

############
# __main__ #
############

if __name__ == "__main__":
    app.run(debug=True)
