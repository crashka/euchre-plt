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

- Show (and edit?) teams for pre-configured tournaments
- Show tournament parameters on dashboard
- Chart-specific axis settings (e.g. min, max, ticks)
- Implement "Cancel Run" and "Restart Run" buttons
- Show interesting aggregate stats below buttons
- Ability to create/save out new tournament configurations
"""

from typing import NamedTuple
from numbers import Number
import shelve
import os.path
import re
import csv
from io import StringIO
from time import time
from importlib import import_module

from flask import Flask, session, request, render_template, Response, abort

from euchplt.utils import typecast
from euchplt.core import cfg
from euchplt.player import Player
from euchplt.team import Team
from euchplt.strategy import Strategy, StrategyRandom
from euchplt.tournament import Tournament, LBStat, LB_PRINT_STATS, RoundRobin, ChallengeLadder
from .smart_tuner import get_strategies

#########
# Setup #
#########

app = Flask(__name__)
app.config.from_prefixed_env()

APP_NAME      = "Tournament Runner"
APP_TEMPLATE  = "tournament_runner.html"
DASH_NAME     = "Tournament Dashboard"
DASH_TEMPLATE = "tournament_dash.html"

APP_DIR       = os.path.dirname(os.path.realpath(__file__))
RESOURCES_DIR = os.path.join(APP_DIR, 'resources')
CONFIG_FILE   = 'tournaments.yml'
CONFIG_PATH   = os.path.join(RESOURCES_DIR, CONFIG_FILE)

####################
# Tournament Stuff #
####################

TOURN_MODPATH = 'euchplt.tournament'
TOURN_MODULE  = import_module(TOURN_MODPATH)
TOURN_CLASSES = {'RoundRobin', 'ChallengeLadder'}

# key = input name; value = default (form input domain, i.e. string representation), if
# `form.get(param) is None`
TOURN_PARAMS = {
    'match_games':   'null',
    'passes':        'null',
    'round_matches': 'null',
    'elim_passes':   'null',
    'elim_pct':      'null',
    'reset_elo':     'false'
}

ELO_PARAMS = {
    'use_margin':    'false',
    'd_value':       'null',
    'k_factor':      'null'
}

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

def save_tourn_info(tourn_id: str, info: dict) -> None:
    """Persist the tournament information (including stats)
    """
    db_file = get_db_file(tourn_id)
    db_path = os.path.join(RESOURCES_DIR, db_file)
    with shelve.open(db_path, flag='c') as db:
        db.update(info)

def retrieve_tourn_info(tourn_id: str) -> dict:
    """Retrieve the tournament information (including stats)
    """
    db_file = get_db_file(tourn_id)
    db_path = os.path.join(RESOURCES_DIR, db_file)
    with shelve.open(db_path) as db:
        # ATTN: can probably do this without the comprehension loop!!!
        info = {k: v for k, v in db.items()}
    return info

FLOAT_PREC = 1

def round_val(val: Number) -> Number:
    """Provide the appropriate level of rounding for the leaderboard or stat value (does
    not change the number type); passthrough for non-numeric types (e.g. bool or str)
    """
    if isinstance(val, float):
        return round(val, FLOAT_PREC)
    return val

################
# Report Stuff #
################

# csv "dialect", currently hardwired (later can specify in `/stats` call, if adding
# support for more interesting formats)
STATS_FMT = 'excel'

FMT_MIMETYPE = {
    'excel':     'text/csv',
    'excel-tab': 'text/csv',
    'unix':      'text/csv',
}

FMT_FILETYPE = {
    'excel':     '.csv',
    'excel-tab': '.tsv',
    'unix':      '.csv',
}

STATS_MIMETYPE = FMT_MIMETYPE[STATS_FMT]
STATS_FILETYPE = FMT_FILETYPE[STATS_FMT]

class StatsReport(NamedTuple):
    """Stats report definition
    """
    id:          int   # contiguous, starting from 0
    name:        str   # human-friendly name for the report
    file_sfx:    str   # tacked onto the end of basename (munged `name`)
    comp_stats:  bool  # computed stats included?
    pos_details: bool  # position details included?
    team_stats:  bool  # team stats (pivoted format)?

    def filename(self, tourn_name: str) -> str:
        """Get file name for the report, based on the tournament name (after collapsing
        all non-alphanumerics to dashes and downcasing)
        """
        basename = re.sub(r'[^A-Za-z0-9]+', '-', tourn_name).strip('-').lower()
        return basename + self.file_sfx + STATS_FILETYPE

STATS_REPORTS = [
    StatsReport(0, "Base Stats",                      '_stats',    False, False, False),
    StatsReport(1, "Base Stats (pos details)",        '_statsdet', False, True,  False),
    StatsReport(2, "Computed Stats",                  '_comps',    True,  False, False),
    StatsReport(3, "Computed Stats (pos details)",    '_compsdet', True,  True,  False),
    StatsReport(4, "Team Stats (pivot)",              '_teams',    True,  False, True),
    StatsReport(5, "Team Stats (pivot, pos details)", '_teamsdet', True,  True,  True)
]

################
# Flask Routes #
################

SUBMIT_FUNCS = [
    'run_tourn',
    'next_pass',
    'cancel_run',
    'restart_run'
]

INIT_TIMER = "0:00"
INIT_START = 0  # to make parseInt() work

POS_STAT = "Position"

CHART_LB_STATS = [
    LBStat.INT_ELO_PTS,
    LBStat.CUR_ELO
]

COL_MAP = {
    str:   "col_txt",
    int:   "col_num",
    float: "col_dec"
}

TD_MAP = {
    str:   "td_txt",
    int:   "td_num",
    float: "td_dec"
}

# REVISIT: this is pretty stupid, need to find a neater way to do this (e.g. allow dummy,
# non-runnable tournaments to be instantiated without specifying teams)!!!
DUMMY_PLAYERS = [
    Player("Dummy 1", StrategyRandom()),
    Player("Dummy 2", StrategyRandom()),
    Player("Dummy 3", StrategyRandom()),
    Player("Dummy 4", StrategyRandom())
]

DUMMY_TEAMS = [
    Team("Dummy 1", DUMMY_PLAYERS[:2]),
    Team("Dummy 2", DUMMY_PLAYERS[2:])
]

def create_team(strat_name: str) -> Team:
    """Create an ad hoc team based on a configured strategy (specified by name)
    """
    strat = Strategy.new(strat_name)
    player1 = Player(strat_name + '_a', strat)
    player2 = Player(strat_name + '_b', strat)
    return Team(strat_name, [player1, player2])

@app.get("/")
def index():
    """Get the configuration info for specified tournament (or an empty form if
    ``sel_tourn`` is not specified in the request)
    """
    tourn       = None
    tourn_fmt   = None
    elo_rating  = None
    custom      = False

    sel_tourn = request.args.get('sel_tourn')
    if sel_tourn:
        if sel_tourn in SEL_CUSTOM:
            tourn_cls = SEL_CUSTOM[sel_tourn]
            tourn = tourn_cls(sel_tourn, DUMMY_TEAMS)
            custom = True
        else:
            tourn = Tournament.new(sel_tourn)

        tourn_fmt  = tourn.__class__.__name__
        elo_rating = tourn.elo_rating

    context = {
        'tourn':       tourn,
        'tourn_fmt':   tourn_fmt,
        'elo_rating':  elo_rating,
        'round_robin': isinstance(tourn, RoundRobin),
        'chal_ladder': isinstance(tourn, ChallengeLadder),
        'custom':      custom,
        'strategies':  get_strategies(get_all=True)
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
    """Start the tournament specified in the form by rendering the initial (empty)
    dashboard, which will then initiate running the individual passes.
    """
    tourn_params = {}
    elo_params = {}
    # NOTE: form input values always come in as a string, so empty input is '' and numeric
    # zero is '0'; `form.get(param) is None` only if `param` input value is not sent from
    # the form at all (e.g. unchecked checkbox)
    for param, dflt in TOURN_PARAMS.items():
        if value := form.get(param, dflt):
            tourn_params[param] = round_val(typecast(value))
    for param, dflt in ELO_PARAMS.items():
        if value := form.get(param, dflt):
            elo_params[param] = round_val(typecast(value))
    if elo_params:
        d_value = elo_params['d_value']
        elo_params['elo_db'] = f"elo_rating_{d_value}.db"
        tourn_params['elo_params'] = elo_params

    tourn_name = form.get('tourn_name')
    tourn_fmt  = form.get('tourn_fmt')
    custom     = typecast(form.get('custom'))
    if custom:
        teams = []
        for idx in range(len(get_strategies(get_all=True))):
            if strategy := form.get(f'strat_{idx}'):
                teams.append(create_team(strategy))
        tourn_cls = getattr(TOURN_MODULE, tourn_fmt)
        tourn = tourn_cls(tourn_name, teams, **tourn_params)
    else:
        tourn = Tournament.new(tourn_name, **tourn_params)
    tourn_id = gen_tourn_id(tourn)
    session['tourn_id'] = tourn_id

    # initialize chart data structure (appended to after each pass)
    ch_data = {}
    ch_data['teams'] = list(tourn.teams)  # team names
    ch_data['stats'] = {}
    for stat in [POS_STAT] + [str(x) for x in CHART_LB_STATS]:
        ch_data['stats'][stat] = {}
        for team in ch_data['teams']:
            ch_data['stats'][stat][team] = []

    save_tourn_info(tourn_id, {'tourn': tourn, 'ch_data': ch_data})

    run_msg = "Starting tournament..."
    context = {
        'tourn':      tourn,
        'lb_col_cls': None,
        'lb_td_cls':  None,
        'lb_header':  None,
        'lb_data':    None,
        'ch_labels':  None,
        'ch_data':    None,
        'timer':      INIT_TIMER,
        'start':      INIT_START,
        'winner':     None,
        'msg':        run_msg,
        'stats_rpts': STATS_REPORTS
    }
    return render_dashboard(context)

def next_pass(form: dict) -> str:
    """Run the next pass for the tournament and render the leaderboard and chart updates
    """
    winner = None
    tourn_id = session['tourn_id']
    info = retrieve_tourn_info(tourn_id)
    tourn = info.get('tourn')
    ch_data = info.get('ch_data')
    assert tourn and ch_data
    # REVISIT: clunky use of local `pass_num`, see note in `RoundRobin.run_pass()`!!!
    pass_num = tourn.pass_num + 1
    assert pass_num < tourn.passes

    lb = tourn.run_pass(pass_num)
    if pass_num + 1 < tourn.passes:
        assert pass_num + 1 == len(tourn.leaderboards)
        pass_msg = f"Completed pass {pass_num + 1} of {tourn.passes}"
    else:
        plural = "s" if len(tourn.winner) > 1 else ""
        winner = ', '.join(tourn.winner)
        pass_msg = f"Tournament complete, winner{plural}: {winner}"

    stats_row = next(iter(lb.values()))
    # note that all of the following include team info in the [0] position
    lb_col_cls = ["col_lbl"] + [COL_MAP[type(v)] for k, v in stats_row.items()
                                if k in LB_PRINT_STATS]
    lb_td_cls  = ["td_lbl"]  + [TD_MAP[type(v)] for k, v in stats_row.items()
                                if k in LB_PRINT_STATS]
    lb_header  = ["Team"]    + [str(k) for k in stats_row.keys()
                                if k in LB_PRINT_STATS]
    lb_data = []
    for idx, (team, stats) in enumerate(lb.items()):
        row = [team] + [round_val(v) for k, v in stats.items()
                        if k in LB_PRINT_STATS]
        lb_data.append(row)
        ch_data['stats'][POS_STAT][team].append(-idx)
        for stat in CHART_LB_STATS:
            ch_data['stats'][str(stat)][team].append(round_val(stats[stat]))

    save_tourn_info(tourn_id, {'tourn': tourn, 'ch_data': ch_data})

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
        'ch_labels':  list(range(1, tourn.passes + 1)),
        'ch_data':    ch_data,
        'timer':      timer,
        'start':      form.get('start'),
        'winner':     winner,
        'msg':        pass_msg,
        'stats_rpts': STATS_REPORTS
    }
    return render_dashboard(context)

def cancel_run(form: dict) -> str:
    """Cancel the run for the tournament and re-render the latest leaderboard and chart
    updates
    """
    raise NotImplementedError("coming soon..")

def restart_run(form: dict) -> str:
    """Restart the run for the tournament (assumed to be either completed or canceled) by
    re-rendering the initial (empty) dashboard, which then will initiate running the
    individual passes.
    """
    raise NotImplementedError("coming soon..")

@app.get("/stats/<int:report_id>")
def download_stats(report_id):
    """Return specified stats report for the tournament, in CSV format
    """
    tourn_id = session['tourn_id']
    info = retrieve_tourn_info(tourn_id)
    tourn = info.get('tourn')
    assert tourn

    # it's okay to download stats for tournaments that did not (or have not) run to
    # completion; we note the number of passes (out of `tourn.passes` total)
    passes_complete = tourn.pass_num + 1

    # for now, whether this throws an `IndexError` is our validation mechanism for
    # `report_id`
    report = STATS_REPORTS[report_id]
    if report.team_stats:
        stats_hdr  = tourn.team_stats_header
        stats_iter = tourn.iter_team_stats
    elif report.comp_stats:
        stats_hdr  = tourn.comp_stats_header
        stats_iter = tourn.iter_comp_stats
    else:
        stats_hdr  = tourn.stats_header
        stats_iter = tourn.iter_stats

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=stats_hdr(report.pos_details),
                            dialect=STATS_FMT, lineterminator=os.linesep)
    writer.writeheader()
    for row in stats_iter(report.pos_details):
        writer.writerow(row)
    stats_out = buffer.getvalue()
    buffer.close()

    return Response(stats_out, mimetype=STATS_MIMETYPE)

################
# App Routines #
################

SEL_SEP = "----------------"

SEL_CUSTOM = {
    "Custom (round robin)": RoundRobin,
    "Custom (challenge ladder)": ChallengeLadder
}

def render_app(context: dict) -> str:
    """Common post-processing of context before rendering the main app page through Jinja
    """
    tourn_list = get_tournaments() + [SEL_SEP] + list(SEL_CUSTOM)

    context['title']      = APP_NAME
    context['tourn_list'] = tourn_list
    context['sel_sep']    = SEL_SEP
    context['help_txt']   = help_txt
    context['ref_links']  = ref_links
    return render_template(APP_TEMPLATE, **context)

def render_dashboard(context: dict) -> str:
    """Render the dashboard, from which the tournament will be run and tracked
    """
    context['title'] = DASH_NAME + f" - {context['tourn'].name}"
    context['help_txt'] = help_txt
    return render_template(DASH_TEMPLATE, **context)

#########################
# Content / Metacontent #
#########################

help_txt = {
    # tournament select
    'tn_0': "from tournaments.yml config file",

    # submit buttons
    'bt_0': "Start tournament and track using the dashboard",

    # download links
    'dl_0': "directly tabulated counts (integer)",
    'dl_1': "directly tabulated counts (integer)",
    'dl_2': "format in Excel as 'Percent' (with decimal places = 1)",
    'dl_3': "format in Excel as 'Percent' (with decimal places = 1)",
    'dl_4': "stats laid out horizontally (suitable for sorting)",
    'dl_5': "stats laid out horizontally (suitable for sorting)"
}

euchplt_pfx = "https://crashka.github.io/euchre-plt/_build/html/euchplt.html#"

ref_links = {
    "Tournament": euchplt_pfx + "module-euchplt.tournament"
}

############
# __main__ #
############

if __name__ == "__main__":
    app.run(debug=True, port=5001)
