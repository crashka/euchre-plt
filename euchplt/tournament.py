#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Module for running various forms of tournaments for strategies and/or teams

Formats:

- Head-to-head
- Round robin
- Challenge ladder
- Single elimination
- Double elimination

Notes:

- Each entrant is a strategy (class + params); players will be generated
  for each team (both on the same strategy)
- Multiple instances of the same strategy can (should?) be entered per tournament
  to indicate determination of results
- Elo is computed within (and across?) tournaments

  - Investigate win- and score-based ELO calculations

- Report cumulative match stats as well
- OPEN ISSUE: should we assign 'seats' at the match level?

To Do:

- Leaderboard stuff should be refactored fully into the base class
- More cleanup of print routines/options
"""

import sys
from enum import Enum
from itertools import chain
from collections.abc import Mapping, Iterator, Iterable, Callable
from typing import TypeVar, TextIO
from numbers import Number
import random
import csv
import os

from .utils import rankdata, parse_argv
from .core import DEBUG, cfg, DataFile, ConfigError
from .team import Team
from .game import GameStat, POS_STATS
from .match import MatchStatXtra, MatchStatIter, Match
from .elo_rating import EloRating

######################
# TournStat/CompStat #
######################

# do the same as for `MatchStat` (see match.py)

class TournStatXtra(Enum):
    MATCHES_PLAYED = "Matches Played"
    MATCHES_WON    = "Matches Won"

    def __str__(self):
        return self.value

TournStat = TournStatXtra | MatchStatXtra | GameStat
def TournStatIter() -> Iterator: return chain(TournStatXtra, MatchStatXtra, GameStat)

# the following represents mapping for *base* stats (computed stats NOT included)
StatsMap = Mapping[TournStat, int]

class CompStat(Enum):
    MATCH_WIN_PCT      = "Match Win Pct"
    GAME_WIN_PCT       = "Game Win Pct"
    DEAL_PASS_PCT      = "Deal Pass Pct"
    CALL_PCT           = "Call Pct"
    CALL_MAKE_PCT      = "Call Make Pct"
    CALL_ALL_5_PCT     = "Call All 5 Pct"
    CALL_EUCH_PCT      = "Call Euchred Pct"
    LONER_CALL_PCT     = "Loner Call Pct"
    LONER_MAKE_PCT     = "Loner Make Pct"
    LONER_FAIL_PCT     = "Loner Fail Pct"
    LONER_EUCH_PCT     = "Loner Euchred Pct"
    NL_CALL_PCT        = "NL Call Pct"
    NL_MAKE_PCT        = "NL Make Pct"
    NL_ALL_5_PCT       = "NL All 5 Pct"
    NL_EUCH_PCT        = "NL Euchred Pct"
    DEF_PCT            = "Defend Pct"
    DEF_EUCH_PCT       = "Defend Euchre Pct"
    DEF_LOSE_PCT       = "Defend Lose Pct"
    DEF_LONER_PCT      = "Defend Loner Pct"
    DEF_LONER_EUCH_PCT = "Defend Loner Euchre Pct"
    DEF_LONER_STOP_PCT = "Defend Loner Stop Pct"
    DEF_LONER_LOSE_PCT = "Defend Loner Lose Pct"
    DEF_ALONE_PCT      = "Defend Alone Pct"
    DEF_ALONE_EUCH_PCT = "Defend Alone Euchre Pct"
    DEF_ALONE_STOP_PCT = "Defend Alone Stop Pct"
    DEF_ALONE_LOSE_PCT = "Defend Alone Lose Pct"

    def __str__(self):
        return self.value

AllStat = TournStatXtra | MatchStatXtra | GameStat | CompStat
def AllStatIter() -> Iterator: return chain(TournStatXtra, MatchStatXtra, GameStat, CompStat)

CS = CompStat
TS = TournStatXtra
MS = MatchStatXtra
GS = GameStat

# for now, only simple percentages are supported (hence, no operator in the
# "formula")--LATER, may get more ambitious about this
CompStatFormulas = {
    CS.MATCH_WIN_PCT      : (TS.MATCHES_WON,       TS.MATCHES_PLAYED),
    CS.GAME_WIN_PCT       : (MS.GAMES_WON,         MS.GAMES_PLAYED),
    CS.DEAL_PASS_PCT      : (GS.DEALS_PASSED,      GS.DEALS_TOTAL),
    CS.CALL_PCT           : (GS.CALLS,             GS.DEALS_TOTAL),
    CS.CALL_MAKE_PCT      : (GS.CALLS_MADE,        GS.CALLS),
    CS.CALL_ALL_5_PCT     : (GS.CALLS_ALL_5,       GS.CALLS),
    CS.CALL_EUCH_PCT      : (GS.CALLS_EUCHRED,     GS.CALLS),
    CS.LONER_CALL_PCT     : (GS.LONERS_CALLED,     GS.CALLS),
    CS.LONER_MAKE_PCT     : (GS.LONERS_MADE,       GS.LONERS_CALLED),
    CS.LONER_FAIL_PCT     : (GS.LONERS_FAILED,     GS.LONERS_CALLED),
    CS.LONER_EUCH_PCT     : (GS.LONERS_EUCHRED,    GS.LONERS_CALLED),
    CS.NL_CALL_PCT        : (GS.NL_CALLS,          GS.CALLS),
    CS.NL_MAKE_PCT        : (GS.NL_CALLS_MADE,     GS.NL_CALLS),
    CS.NL_ALL_5_PCT       : (GS.NL_CALLS_ALL_5,    GS.NL_CALLS),
    CS.NL_EUCH_PCT        : (GS.NL_CALLS_EUCHRED,  GS.NL_CALLS),
    CS.DEF_PCT            : (GS.DEFENSES,          GS.DEALS_TOTAL),
    CS.DEF_EUCH_PCT       : (GS.DEF_EUCHRES,       GS.DEFENSES),
    CS.DEF_LOSE_PCT       : (GS.DEF_LOSSES,        GS.DEFENSES),
    CS.DEF_LONER_PCT      : (GS.DEF_LONERS,        GS.DEFENSES),
    CS.DEF_LONER_EUCH_PCT : (GS.DEF_LONER_EUCHRES, GS.DEF_LONERS),
    CS.DEF_LONER_STOP_PCT : (GS.DEF_LONER_STOPS,   GS.DEF_LONERS),
    CS.DEF_LONER_LOSE_PCT : (GS.DEF_LONER_LOSSES,  GS.DEF_LONERS),
    CS.DEF_ALONE_PCT      : (GS.DEF_ALONES,        GS.DEFENSES),
    CS.DEF_ALONE_EUCH_PCT : (GS.DEF_ALONE_EUCHRES, GS.DEF_ALONES),
    CS.DEF_ALONE_STOP_PCT : (GS.DEF_ALONE_STOPS,   GS.DEF_ALONES),
    CS.DEF_ALONE_LOSE_PCT : (GS.DEF_ALONE_LOSSES,  GS.DEF_ALONES)
}

# generate list of CompStat entries that can be computed by position
# (i.e. both operands are in POS_STATS)
POS_COMP_STATS = set(stat for stat, opnds in CompStatFormulas.items() if POS_STATS >= set(opnds))

#####################
# Leaderboard stuff #
#####################

class LBStat(Enum):
    MATCHES      = "Matches"
    WINS         = "Wins"
    LOSSES       = "Losses"
    WIN_PCT      = "Win %"
    ELO_PTS      = "Elo Points"
    CUR_ELO      = "Elo Rating"
    INT_MATCHES  = "Matches (interval)"
    INT_WINS     = "Wins (interval)"
    INT_LOSSES   = "Losses (interval)"
    INT_WIN_PCT  = "Win % (interval)"
    INT_ELO_PTS  = "Elo Points (interval)"
    DELTA_ELO    = "Elo Rating (delta)"
    WINS_RANK    = "Wins Rank"
    WIN_PCT_RANK = "Win % Rank"
    ELO_PTS_RANK = "Elo Points Rank"
    CUR_ELO_RANK = "Elo Rating Rank"

    def __str__(self) -> str:
        return self.value

LB_PRINT_STATS = {LBStat.WINS,
                  LBStat.LOSSES,
                  LBStat.WIN_PCT,
                  LBStat.ELO_PTS,
                  LBStat.CUR_ELO,
                  LBStat.WIN_PCT_RANK,
                  LBStat.CUR_ELO_RANK}

LBStats     = dict[LBStat, list[Number]]  # LB stats for a team
Leaderboard = dict[str, LBStats]          # indexed by team name

##############
# Tournament #
##############

# superset of tournament subdivisions that subclasses may coopt for
# their own usage/interpretation (other than `MATCH`, of course)
TournUnit = Enum('TournUnit', 'MATCH ROUND PASS TOURNAMENT')

class Tournament:
    """Abstract base class, cannot be instantiated directly.
    """
    # params/config
    name:           str
    teams:          dict[str, Team]  # indexed by team name
    match_games:    int | None       # num games needed to win match
    # NOTE the different naming convention for position-related stats
    # stuff here, compared to Game and Match classes (should probably
    # make it all consistent at some point)!!!
    pos_stats:      set[GameStat]
    pos_comp_stats: set[CompStat]
    # callbacks for each "unit" managed by base class
    callbacks:      dict[TournUnit, list[Callable]]

    # state, etc.
    pass_num:       int
    # NOTE: matches are appended by `play_match()`, but the parent class has
    # no additional interest in this list; it is up to subclasses to figure
    # out how/whether they want to use it for reporting, analysis, etc.
    matches:        list[Match]
    team_score:     dict[str, list[Number]]  # [matches, elo_points], indexed as `teams`
    team_score_opp: dict[str, dict[str, list[Number]]]     # same as previous, per opponent team
    team_stats:     dict[str, dict[TournStat, int]]        # indexed as `teams`
    team_pos_stats: dict[str, dict[TournStat, list[int]]]  # tabulate stats by call_pos
    winner:         tuple[str, ...] | None
    results:        list[str] | None
    # elimination, leaderboard, and elo stuff managed by subclasses
    eliminated:     set[str]                 # team names
    leaderboards:   list[Leaderboard]
    lb_base:        Leaderboard | None
    lb_prev:        Leaderboard | None
    elo_rating:     EloRating | None

    @classmethod
    def new(cls, tourn_name: str, **kwargs) -> 'Tournament':
        """Return instantiated Tournament object based on name; format, teams, and
        parameter defaults are specified in the config file (teams and params can
        be overridden by `kwargs`)
        """
        tournaments = cfg.config('tournaments')
        if tourn_name not in tournaments:
            raise RuntimeError(f"Tournament '{tourn_name}' is not known")
        tourn_info   = tournaments[tourn_name]
        class_name   = tourn_info.get('tourn_class')
        tourn_params = tourn_info.get('tourn_params') or {}
        if not class_name:
            raise ConfigError(f"'tourn_class' not specified for tournament '{tourn_name}'")
        tourn_class = globals()[class_name]
        if not issubclass(tourn_class, cls):
            raise ConfigError(f"'{tourn_class.__name__}' not subclass of '{cls.__name__}'")

        # `teams` is not part of `tourn_params`, but can be specified in `kwargs`
        teams = kwargs.pop('teams', None) or tourn_info.get('teams')
        tourn_params.update(kwargs)
        return tourn_class(tourn_name, teams, **tourn_params)

    def __init__(self, name: str, teams: Iterable[str] | Iterable[Team], **kwargs):
        """Tournament teams can either be specified by name (in the config file) or
        instantiated `Team` objects (format must be consistent within the iterable)
        """
        self.name = name
        self.teams = {}
        # idx is used below as a count of the inbound teams
        for idx, team in enumerate(teams):
            if isinstance(team, str):
                team = Team(team)
            self.teams[team.name] = team
        if len(self.teams) < 2:
            raise RuntimeError("At least two teams must be specified")
        if len(self.teams) < idx + 1:
            raise RuntimeError("Team names must be unique")

        class_name = type(self).__name__
        base_params = cfg.config('base_tourn_params')
        if class_name not in base_params:
            raise ConfigError(f"Tournament class '{class_name}' does not exist")
        for key, base_value in base_params[class_name].items():
            # note that empty values in kwargs should override base values
            setattr(self, key, kwargs[key] if key in kwargs else base_value)

        self.pos_stats      = set(GameStat[s.upper()] for s in self.pos_stats or [])
        self.pos_comp_stats = set(CompStat[s.upper()] for s in self.pos_comp_stats or [])
        for stat in self.pos_comp_stats:
            if missing := set(CompStatFormulas[stat]) - self.pos_stats:
                raise ConfigError(f"Missing dependency {', '.join(missing)} for stat '{stat.name}'")

        # callbacks may be added by the subclass or by the caller; they are invoked by the
        # base class in the corresponding "tabulate" method (which must be called by the
        # subclass)--callbacks take the same arguments as their corresponding "tabulate"
        # call plus additional kwargs, as needed
        self.callbacks = {}
        for unit in TournUnit:
            self.callbacks[unit] = []

        self.pass_num       = -1
        self.matches        = []
        self.team_score     = {name: [0, 0.0] for name in self.teams}
        self.team_score_opp = {name: {opp: [0, 0.0] for opp in self.teams if opp is not name}
                               for name in self.teams}
        self.team_stats     = {name: {stat: 0 for stat in TournStatIter()}
                               for name in self.teams}
        self.team_pos_stats = {name: {stat: [0] * 8 for stat in self.pos_stats}
                               for name in self.teams}
        self.winner         = None
        self.results        = None
        self.eliminated     = set()
        self.leaderboards   = []
        self.lb_base        = None
        self.lb_prev        = None
        self.elo_rating     = None

    def add_callback(self, unit: TournUnit, cb: Callable) -> None:
        """Add callback at the specific tournament "unit" level; will be invoked by the
        base class as part of the "tabulate" process
        """
        self.callbacks[unit].append(cb)

    def tabulate(self, match: Match, **kwargs) -> None:
        """Tabulate the result of a single match.  Subclasses may choose to implement and
        invoke additional methods for tabulating after completing rounds, stages, or any
        other subdivision for the specific format.
        """
        for i, team in enumerate(match.teams):
            name = team.name
            opp = match.teams[i ^ 0x01].name
            self.team_stats[name][TS.MATCHES_PLAYED] += 1
            self.team_score[name][1] += match.score[i] / sum(match.score)
            self.team_score_opp[name][opp][1] += match.score[i] / sum(match.score)
            if team == match.winner[1]:
                self.team_stats[name][TS.MATCHES_WON] += 1
                self.team_score[name][0] += 1
                self.team_score_opp[name][opp][0] += 1

            for stat in MatchStatIter():
                self.team_stats[name][stat] += match.stats[i][stat]
                if stat in self.pos_stats:
                    my_stat_list = self.team_pos_stats[name][stat]
                    match_stat_list = match.pos_stats[i][stat]
                    for j in range(8):
                        my_stat_list[j] += match_stat_list[j]

        for cb in self.callbacks[TournUnit.MATCH]:
            cb(match, **kwargs)

    def tabulate_round(self, round_num: int, matches: list[Match], **kwargs) -> None:
        """Base class only calls appropriate callbacks, since the meaning of a "round" is
        up to the subclass
        """
        for cb in self.callbacks[TournUnit.ROUND]:
            cb(round_num, matches, **kwargs)

    def tabulate_pass(self, pass_num: int, matches: list[Match], **kwargs) -> None:
        """Base class only calls appropriate callbacks, since the meaning of a "pass" is
        up to the subclass
        """
        for cb in self.callbacks[TournUnit.PASS]:
            cb(pass_num, matches, **kwargs)

        assert self.pass_num == pass_num - 1
        self.pass_num = pass_num

    def tabulate_tournament(self, **kwargs) -> None:
        """Base class only calls appropriate callbacks
        """
        for cb in self.callbacks[TournUnit.TOURNAMENT]:
            cb(**kwargs)

    @staticmethod
    def score_key(x):
        """Sort by wins then Elo points (this algo works because Elo points will
        always be less than wins)
        """
        return x[1][0] * x[1][0] + x[1][1]

    def set_winner(self) -> None:
        """This method is overrideable for tournament formats where the results/winner(s)
        are determined in a way other than match wins
        """
        thresh = 0.1  # for floating point comparison
        # determine winner by number of matches won (element score_item[1][0])
        scores = sorted(self.team_score.items(), key=self.score_key, reverse=True)
        top_score_item = scores[0]
        winners: list[str] = [top_score_item[0]]
        for score_item in scores[1:]:
            if top_score_item[1][0] - score_item[1][0] > thresh:
                break
            winners.append(score_item[0])

        self.winner = tuple(winners)
        self.results = [s[0] for s in scores]

    def set_lb_base(self, lb_current: Leaderboard) -> None:
        """Set baseline for leaderboard, for tracking movement between resets
        (e.g. elimination events, for RoundRobin)
        """
        self.lb_base = {}
        for name, cur_stats in lb_current.items():
            stats = self.team_stats[name]
            score = self.team_score[name]
            base_stats = {}
            base_stats[LBStat.MATCHES] = stats[TS.MATCHES_PLAYED]
            base_stats[LBStat.WINS]    = score[0]
            base_stats[LBStat.ELO_PTS] = score[1]
            base_stats[LBStat.CUR_ELO] = cur_stats[LBStat.CUR_ELO]
            self.lb_base[name] = base_stats

    def set_lb_prev(self, lb_current: Leaderboard) -> None:
        """Set pass-level baseline for leaderboard, for tracking movement between updates
        """
        self.lb_prev = {}
        for name, cur_stats in lb_current.items():
            stats = self.team_stats[name]
            score = self.team_score[name]
            prev_stats = {}
            prev_stats[LBStat.MATCHES] = stats[TS.MATCHES_PLAYED]
            prev_stats[LBStat.WINS]    = score[0]
            prev_stats[LBStat.ELO_PTS] = score[1]
            prev_stats[LBStat.CUR_ELO] = cur_stats[LBStat.CUR_ELO]
            self.lb_prev[name] = prev_stats

    @staticmethod
    def lb_key(x):
        """Same algo as `score_key()`
        """
        return x[1][LBStat.WINS] * x[1][LBStat.WINS] + x[1][LBStat.ELO_PTS]

    def get_leaderboard(self, teams: Iterable[Team] = None, key: Callable = None,
                        reverse: bool = True) -> Leaderboard:
        """Return list of leaderboard stats for each team, indexed by name, and sorted
        as specified by `key` and `reverse`.  Stats list is indexed as the enumeration
        of `LBStat` members.
        """
        teams = teams or self.teams
        key = key or self.lb_key

        team_idx    = {}  # name -> idx
        lb_stats    = {}  # name -> list[stat_val]
        lb_out      = {}  # name -> dict[LBStat, stat_val]
        wins_vec    = []
        win_pct_vec = []
        elo_pts_vec = []
        cur_elo_vec = []

        for idx, name in enumerate(teams):
            team_idx[name] = idx
            stats          = self.team_stats[name]
            score          = self.team_score[name]

            # compute current leaderboard stats relative to baseline (if set)
            if self.lb_base:
                base_stats = self.lb_base[name]
                match_off  = base_stats[LBStat.MATCHES]
                wins_off   = base_stats[LBStat.WINS]
                pts_off    = base_stats[LBStat.ELO_PTS]
            else:
                match_off  = 0
                wins_off   = 0
                pts_off    = 0

            matches        = stats[TS.MATCHES_PLAYED] - match_off
            wins           = score[0] - wins_off
            losses         = matches - wins
            win_pct        = wins / matches * 100.0
            elo_pts        = score[1] - pts_off
            cur_elo        = self.elo_rating.team_ratings[name] if self.elo_rating else -1
            lb_stats[name] = [matches, wins, losses, win_pct, elo_pts, cur_elo]

            wins_vec.append(wins)
            win_pct_vec.append(win_pct)
            elo_pts_vec.append(elo_pts)
            cur_elo_vec.append(cur_elo)

            # compute leaderboard stats for the interval; NOTE, we are reusing
            # some variables here for convenience/consistency, but this really
            # needs to be refactored at some point--BEWARE the subtle changes
            # here (related to Elo) compared to baseline processing above!!!
            if self.lb_prev:
                prev_stats = self.lb_prev[name]
                match_off  = prev_stats[LBStat.MATCHES]
                wins_off   = prev_stats[LBStat.WINS]
                pts_off    = prev_stats[LBStat.ELO_PTS]
                elo_off    = prev_stats[LBStat.CUR_ELO]
            else:
                match_off  = 0
                wins_off   = 0
                pts_off    = 0
                elo_off    = 1500

            matches        = stats[TS.MATCHES_PLAYED] - match_off
            wins           = score[0] - wins_off
            losses         = matches - wins
            win_pct        = wins / matches * 100.0
            elo_pts        = score[1] - pts_off
            int_elo        = cur_elo - elo_off
            int_stats      = [matches, wins, losses, win_pct, elo_pts, int_elo]
            lb_stats[name].extend(int_stats)

        wins_rank    = rankdata(wins_vec, method='min')
        win_pct_rank = rankdata(win_pct_vec, method='min')
        elo_pts_rank = rankdata(elo_pts_vec, method='min')
        cur_elo_rank = rankdata(cur_elo_vec, method='min')
        for name, idx in team_idx.items():
            ranks = [wins_rank[idx], win_pct_rank[idx], elo_pts_rank[idx], cur_elo_rank[idx]]
            lb_stats[name].extend(ranks)
            lb_out[name] = dict(zip(LBStat, lb_stats[name]))

        lb_sorted = sorted(lb_out.items(), key=key, reverse=reverse)
        return dict(lb_sorted)

    def play_match(self, matchup: Iterable[str]) -> None:
        """Uniform/common method for conducting a match within the tournament
        """
        teams = (self.teams[t] for t in matchup)
        match = Match(teams, match_games=self.match_games)
        self.matches.append(match)
        match.play()
        self.tabulate(match)

    def play(self, **kwargs) -> None:
        """Abstract method to be implemented by all subclasses, who should
        then invoke `play_match()` to conduct each of the matchups created
        for the tournament type
        """
        raise NotImplementedError("Can't call abstract method")

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """This method can be overridden by subclasses to add additional information,
        but parent function should be invoked at the top
        """
        verbose = max(verbose, DEBUG)

        if verbose:
            print("Teams:", file=file)
            for i, team in enumerate(self.teams.values()):
                print(f"  {team}", file=file)
                for j, player in enumerate(team.players):
                    print(f"    {player}", file=file)

        self.print_score(file=file, vs_opp=(verbose > 0))
        if verbose:
            self.print_stats(file=file, by_pos=(verbose > 1))
        if self.elo_rating:
            self.elo_rating.print(file=file, verbose=verbose)

    def print_score(self, file: TextIO = sys.stdout, vs_opp: bool = False) -> None:
        """Include record against all other teams, if `vs_opp` is specified
        """
        print("Tournament Score:", file=file)
        for name in self.results:
            score = self.team_score[name]
            print(f"  {name}: {score[0]} ({score[1]:.2f})", file=file)
            if vs_opp:
                for opp_name, score in self.team_score_opp[name].items():
                    opp_score = self.team_score_opp[opp_name][name]
                    print(f"    vs {opp_name}: {score[0]} - {opp_score[0]} "
                          f"({score[1]:.2f} - {opp_score[1]:.2f})", file=file)

        if not self.winner:
            return

        plural = "s" if len(self.winner) > 1 else ""
        print(f"Tournament Winner{plural}:\n  {', '.join(self.winner)}")

    def print_stats(self, file: TextIO = sys.stdout, by_pos: bool = False) -> None:
        """
        """
        CSF = CompStatFormulas
        NOT_APPLICABLE = "n/a"
        print("Tournament Stats:", file=file)
        for name in self.teams:
            base_stats = self.team_stats[name]
            print(f"  {name}:", file=file)
            for stat in TournStatIter():
                print(f"    {stat.value + ':':24} {base_stats[stat]:8}", file=file)
                if by_pos and stat in self.pos_stats:
                    pos_stat = self.team_pos_stats[name][stat]
                    stat_tot = sum(pos_stat)
                    for i in range(8):
                        pos_str = f"Pos {i}:"
                        pct_str = f" ({pos_stat[i] / stat_tot * 100.0:5.2f}%)" if stat_tot else ""
                        print(f"      {pos_str:22} {pos_stat[i]:8}{pct_str}", file=file)
            for stat in CompStat:
                num = base_stats[CSF[stat][0]]
                den = base_stats[CSF[stat][1]]
                if not den:
                    print(f"    {stat.value + ':':24}   ", NOT_APPLICABLE, file=file)
                    continue
                print(f"    {stat.value + ':':24} {num / den * 100.0:7.2f}%", file=file)
                if by_pos and stat in self.pos_comp_stats:
                    nums = self.team_pos_stats[name][CSF[stat][0]]
                    dens = self.team_pos_stats[name][CSF[stat][1]]
                    for i in range(8):
                        if not dens[i]:
                            continue
                        pos_str = f"Pos {i}:"
                        print(f"      {pos_str:22} {nums[i] / dens[i] * 100.0:7.2f}%", file=file)

    def print_lb(self, label: str = None, file: TextIO = sys.stdout) -> None:
        """Prints the current leaderboard (assumed to be previously sorted)
        """
        label_str = f"{label} " if label else ""
        print(f"{label_str}Leaderboard:")
        stats_header = '\t'.join([f"{s.value:10}" for s in LBStat if s in LB_PRINT_STATS])
        print(f"  {'Team':15}\t{stats_header}")

        for name, lb_stats in self.leaderboards[-1].items():
            stat_vals = []
            for i, stat in enumerate(LBStat):
                if stat not in LB_PRINT_STATS:
                    continue
                if isinstance(lb_stats[stat], float):
                    stat_vals.append(f"{lb_stats[stat]:<10.1f}")
                else:
                    stat_vals.append(f"{str(lb_stats[stat]):10}")
            stats_str = '\t'.join(stat_vals)
            print(f"  {name:15}\t{stats_str}", file=file)

    def stats_header(self) -> list[str]:
        """Header fields must correspond to the keys for `iter_stats()` yield
        """
        def expand(stat_iter: Iterable[AllStat]) -> str:
            for stat in stat_iter:
                yield str(stat)
                if stat in self.pos_stats | self.pos_comp_stats:
                    for i in range(8):
                        yield str(stat) + f" (Pos {i})"

        TEAM_COL = 'Team'
        fields = [TEAM_COL] + list(expand(AllStatIter()))
        return fields

    def iter_stats(self) -> dict[str, Number]:
        """Keys for stats output correspond to the field names returned by `stats_header()`
        """
        def stats_gen(stats_map: StatsMap, pos_stats_map: StatsMap) -> tuple[str, int]:
            for stat, value in stats_map.items():
                yield str(stat), value
                if stat in self.pos_stats:
                    pos_stat = pos_stats_map[stat]
                    for i in range(8):
                        field_name = str(stat) + f" (Pos {i})"
                        yield field_name, pos_stat[i]

        def comp_stats_gen(stats_map: StatsMap, pos_stats_map: StatsMap) -> tuple[str, int]:
            """
            """
            CSF = CompStatFormulas
            for stat in CSF:
                num = stats_map[CSF[stat][0]]
                den = stats_map[CSF[stat][1]]
                yield str(stat), num / den if den else None
                if stat in self.pos_comp_stats:
                    nums = pos_stats_map[CSF[stat][0]]
                    dens = pos_stats_map[CSF[stat][1]]
                    for i in range(8):
                        field_name = str(stat) + f" (Pos {i})"
                        yield field_name, nums[i] / dens[i] if dens[i] else None

        TEAM_COL = 'Team'
        for name in self.teams:
            base_stats = stats_gen(self.team_stats[name], self.team_pos_stats[name])
            comp_stats = comp_stats_gen(self.team_stats[name], self.team_pos_stats[name])
            stats_row = {TEAM_COL: name} | dict(base_stats) | dict(comp_stats)
            yield stats_row

##############
# HeadToHead #
##############

class HeadToHead(Tournament):
    pass

##############
# RoundRobin #
##############

DFLT_PASSES     = 1
DFLT_ELO_UPDATE = 'PASS'

T = TypeVar('T')
TO = T | None

class RoundRobin(Tournament):
    """This is a modified round robin format wherein multiple passes through the
    field is supported.  In addition, the lowest ranked teams may be eliminated
    after each `elim_passes` cycle, if specified.  Note that `elim_pct` is
    computed relative to the original field size, so the number of teams
    eliminated each cycle is always the same.
    """
    # params
    passes:        int
    elim_passes:   int
    elim_pct:      int
    reset_elo:     bool
    elo_update:    TournUnit
    elo_params:    dict[str, str | Number]

    # state, etc.
    elim_num:      int        # number to eliminate per cycle
    elim_order:    list[str]  # team names

    @staticmethod
    def get_matchups(teams: Iterable[T]) -> Iterator[list[tuple[TO, TO]]]:
        """Note that `None` in a matchup represents a bye
        """
        def rotate(my_list: list[TO], n: int = 1) -> list[TO]:
            return my_list[n:] + my_list[:n]

        def matchups(my_field: list[TO]) -> Iterator[tuple[TO, TO]]:
            home = my_field[:n_matchups]
            away = reversed(my_field[n_matchups:])
            return zip(home, away)

        teams_list = list(teams)
        if len(teams_list) % 2 == 1:
            teams_list.append(None)
        random.shuffle(teams_list)
        n_teams = len(teams_list)
        n_matchups = n_teams // 2
        list_head = teams_list[:1]
        list_tail = teams_list[1:]

        for _ in range(n_teams - 1):
            field = list_head + list_tail
            yield matchups(field)
            list_tail = rotate(list_tail)

    def __init__(self, name: str, teams: Iterable[str] | Iterable[Team], **kwargs):
        """
        """
        super().__init__(name, teams, **kwargs)
        # REVISIT: there _shouldn't_ be any empty values here, but apply defaults
        # just in case (or should we actually just let things blow up???)
        self.passes = self.passes or DFLT_PASSES
        self.reset_elo = self.reset_elo or False
        self.elo_params = self.elo_params or {}
        self.elo_params['reset_ratings'] = self.reset_elo
        self.elo_rating = EloRating(self.teams.values(), self.elo_params)
        elo_update = self.elo_update or DFLT_ELO_UPDATE
        self.elo_update = TournUnit[elo_update.upper()]
        if self.elim_passes:
            self.elim_num = round(len(self.teams) * self.elim_pct / 100.0)
        self.elim_order = []

    def tabulate(self, match: Match) -> None:
        """
        """
        super().tabulate(match)
        if self.elo_update == TournUnit.MATCH:
            self.elo_rating.update([match])

    def tabulate_round(self, round_num: int, matches: list[Match]) -> None:
        """For now, we don't do anything here--since every teams plays at most
        once per round, this is the same as per-match tabulation
        """
        if self.elo_update == TournUnit.ROUND:
            self.elo_rating.update(matches, collective=True)
        super().tabulate_round(round_num, matches)

    def tabulate_pass(self, pass_num: int, matches: list[Match]) -> None:
        """Do collective Elo ratings updates (if requested), update leaderboards, and
        perform team elimination (if/as specified)
        """
        if self.elo_update == TournUnit.PASS:
            self.elo_rating.update(matches, collective=True)

        num_passes = pass_num + 1
        lb = self.get_leaderboard(set(self.teams.keys()) - self.eliminated)
        self.leaderboards.append(lb)
        self.set_lb_prev(lb)

        if self.elim_passes and num_passes % self.elim_passes == 0:
            # don't go below `elim_pct` teams remaining
            if len(self.teams) - len(self.eliminated) >= self.elim_num * 2:
                lb_iter = lb.items()
                lb_sorted = sorted(lb_iter, key=self.lb_key, reverse=True)
                leader_teams = [s[0] for s in lb_sorted if s[0] not in self.eliminated]
                eliminate = list(reversed(leader_teams[-self.elim_num:]))
                self.elim_order.extend(eliminate)
                self.eliminated.update(eliminate)
                self.set_lb_base(lb)
        super().tabulate_pass(pass_num, matches)
        self.matches.clear()

    def print_pass_update(self, pass_num: int, matches: list[Match]) -> None:
        """Pass-level callback used to print leaderboard
        """
        self.print_lb(f"Pass {pass_num}")

    def set_winner(self) -> None:
        """
        """
        lb_iter = self.leaderboards[-1].items()
        lb_sorted = sorted(lb_iter, key=self.lb_key, reverse=True)
        top_lb_item = lb_sorted[0]
        winners: list[str] = [top_lb_item[0]]
        for lb_item in lb_sorted[1:]:
            if lb_item[1][LBStat.WINS] < top_lb_item[1][LBStat.WINS]:
                break
            winners.append(lb_item[0])

        self.winner = tuple(winners)
        self.results = [t[0] for t in lb_sorted] + list(reversed(self.elim_order))
        self.elo_rating.persist()
        super().tabulate_tournament()

    def play(self, **kwargs) -> None:
        """Implemented by iterating through round robin passes
        """
        self.add_callback(TournUnit.PASS, self.print_pass_update)
        for _ in self.iter_passes(**kwargs):
            pass

    def iter_passes(self, **kwargs) -> Leaderboard:
        """Generator for iterating passes
        """
        for pass_num in range(self.passes):
            yield self.run_pass(pass_num, **kwargs)

    def run_pass(self, pass_num: int, **kwargs) -> Leaderboard:
        """Run the specified "pass" (single round robin) for the tournament, and return
        the resulting leaderboard; for a pass, each team plays each other team in a match
        up to ``match_games`` games.  The final leaderboard represents the overall results
        for the tournament.

        This interface is a little clunky (in that ``pass_num`` is actually not needed,
        since it is kept in the object instance), but we'll keep it this way (for now) to
        ensure integrity on the caller side.

        Note, we truncate ``self.matches`` (in ``tabulate_pass()``) to avoid infinite memory
        consumption.
        """
        assert pass_num == len(self.leaderboards)
        active_teams = set(self.teams.keys()) - self.eliminated
        pass_start = len(self.matches)

        for round_num, matchups in enumerate(self.get_matchups(active_teams)):
            round_start = len(self.matches)
            for matchup in matchups:
                if None in matchup:
                    continue
                self.play_match(matchup)  # note this invokes `tabulate()`
            self.tabulate_round(round_num, self.matches[round_start:])
        self.tabulate_pass(pass_num, self.matches[pass_start:])

        if pass_num == self.passes - 1:
            self.set_winner()
        return self.leaderboards[-1]

###################
# ChallengeLadder #
###################

DFLT_ROUND_MATCHES = 1

class ChallengeLadder(Tournament):
    """
    """
    # params
    passes:        int
    round_matches: int
    seeded:        bool
    reset_elo:     bool
    elo_update:    TournUnit
    elo_params:    dict[str, str | Number]

    # state, etc.
    ladder:        list[str]
    ladder_hist:   list[dict[str, int]]  # pos, indexed by round, team name
    round_score:   dict[str, int]        # matches, indexed by team name
    round_winners: list[str]

    def __init__(self, name: str, teams: Iterable[str] | Iterable[Team], **kwargs):
        """
        """
        super().__init__(name, teams, **kwargs)
        # REVISIT: there _shouldn't_ be any empty values here, but apply defaults
        # just in case (or should we actually just let things blow up???)
        self.passes = self.passes or DFLT_PASSES
        self.round_matches = self.round_matches or DFLT_ROUND_MATCHES
        self.seeded = self.seeded or False
        self.reset_elo = self.reset_elo or False
        self.elo_params = self.elo_params or {}
        self.elo_params['reset_ratings'] = self.reset_elo
        self.elo_rating = EloRating(self.teams.values(), self.elo_params)
        elo_update = self.elo_update or DFLT_ELO_UPDATE
        self.elo_update = TournUnit[elo_update.upper()]
        self.round_score = {}
        self.leaderboards = []
        self.lb_base = None
        # start ladder with current Elo ratings, unless resetting or teams
        # already arranged in seeded order
        if not self.seeded and not self.reset_elo:
            self.ladder = [t for t, _ in self.elo_rating.get_sorted()]
        else:
            self.ladder = list(self.teams.keys())
        self.ladder_hist = [{t: pos for pos, t in enumerate(self.ladder)}]

    def get_matchup(self, round_num: int) -> tuple[Team, Team]:
        """
        """
        # last team for round_num = 0, going up the ladder each round
        chal = len(self.teams) - round_num - 1
        matchup = (self.ladder[chal], self.ladder[chal-1])

        assert not self.round_score
        self.round_score = {t: 0 for t in matchup}
        return matchup

    def tabulate(self, match: Match) -> None:
        """
        """
        super().tabulate(match)
        if self.elo_update == TournUnit.MATCH:
            self.elo_rating.update([match])

        team = match.winner[1]
        self.round_score[team.name] += 1

    def tabulate_round(self, round_num: int, matches: list[Match]) -> None:
        """This is the level we update Elo ratings for this tournament format
        """
        if self.elo_update == TournUnit.ROUND:
            self.elo_rating.update(matches, collective=True)

        score_items = sorted(self.round_score.items(), key=lambda s: s[1], reverse=True)
        winner = score_items[0][0]
        loser  = score_items[1][0]
        # swap ladder positions if challenger wins
        chal = len(self.teams) - round_num - 1
        if winner == self.ladder[chal]:
            self.ladder[chal-1:chal+1] = self.ladder[chal::-1][:2]
            winner += " (c)"
            loser  += "    "
        else:
            winner += "    "
            loser  += " (c)"

        scores = [s[1] for s in score_items]
        super().tabulate_round(round_num, matches, teams=[winner, loser], scores=scores)
        self.round_score = {}

    def print_round_update(self, round_num: int, matches: list[Match],
                           teams: list[str], scores: list[int]) -> None:
        """Round-level callback used to print last ladder traversal
        """
        winner, loser = teams
        print(f"Round {round_num:2}: {winner} def. {loser}\t{scores[0]} - {scores[1]}")

    def tabulate_pass(self, pass_num: int, matches: list[Match]) -> None:
        """Recompute leaderboard stats and report standings after each pass
        """
        if self.elo_update == TournUnit.PASS:
            self.elo_rating.update(matches, collective=True)

        team_pos = {t: pos for pos, t in enumerate(self.ladder)}
        self.ladder_hist.append(team_pos)

        lb = self.get_leaderboard(self.teams, key=lambda s: team_pos[s[0]], reverse=False)
        self.leaderboards.append(lb)
        self.set_lb_prev(lb)

        super().tabulate_pass(pass_num, matches)
        self.matches.clear()

    def print_pass_update(self, pass_num: int, matches: list[Match]) -> None:
        """Pass-level callback used to print leaderboard
        """
        print(f"Pass {pass_num} Results:")
        prev_pos = self.ladder_hist[-2]
        for pos, team in enumerate(self.ladder):
            move = prev_pos[team] - pos
            print(f"  {team} ({move:+d})")

        self.print_lb(f"Pass {pass_num}")

    def set_winner(self) -> None:
        """
        """
        self.winner = tuple((self.ladder[0],))
        self.results = self.ladder
        self.elo_rating.persist()
        super().tabulate_tournament()

    def play(self, **kwargs) -> None:
        """Implemented by iterating through challenge ladder passes
        """
        self.add_callback(TournUnit.ROUND, self.print_round_update)
        self.add_callback(TournUnit.PASS, self.print_pass_update)
        for _ in self.iter_passes(**kwargs):
            pass

    def iter_passes(self, **kwargs) -> Leaderboard:
        """Generator for iterating passes
        """
        for pass_num in range(self.passes):
            yield self.run_pass(pass_num, **kwargs)

    def run_pass(self, pass_num: int, **kwargs) -> Leaderboard:
        """Run the specified "pass" (single traversal of the challenge ladder, from bottom
        to top) for the tournament, and return the resulting leaderboard; for a pass, each
        team plays at least once (more than once if advancing positions).  The final
        leaderboard represents the overall results for the tournament.

        This interface is a little clunky (in that ``pass_num`` is actually not needed,
        since it is kept in the object instance), but we'll keep it this way (for now) to
        ensure integrity on the caller side (same as with ``RoundRobin``).

        Also as with ``RoundRobin``, we clear ``self.matches`` after doing pass-level
        tabulation to avoid excessive memory consumption.  Elo updates are hard-wired to
        happen after each round of head-to-head challenge matches.
        """
        assert pass_num == len(self.leaderboards)
        num_teams = len(self.teams)
        pass_start = len(self.matches)

        for round_num in range(num_teams - 1):
            round_start = len(self.matches)
            matchup = self.get_matchup(round_num)
            while max(self.round_score.values()) < self.round_matches:
                self.play_match(matchup)  # note this invokes `tabulate()`
            self.tabulate_round(round_num, self.matches[round_start:])
        self.tabulate_pass(pass_num, self.matches[pass_start:])

        if pass_num == self.passes - 1:
            self.set_winner()
        return self.leaderboards[-1]

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """
        """
        print(f"Tournament Results:")
        init_ladder = self.ladder_hist[0]
        for pos, team in enumerate(self.ladder):
            move = init_ladder[team] - pos
            print(f"  {team} ({move:+d})")
        super().print(file, verbose)

#####################
# SingleElimination #
#####################

class SingleElimination(Tournament):
    pass

#####################
# DoubleElimination #
#####################

class DoubleElimination(Tournament):
    pass

########
# main #
########

from os import environ

from .card import set_seed as set_card_seed

PROFILER = environ.get('EUCH_PROFILER')
if PROFILER and PROFILER == 'pyinstrument':
    from pyinstrument import Profiler
    profiler = Profiler(interval=0.001)
else:
    profiler = None

def round_robin_bracket(*args, **kwargs) -> int:
    """Print out brackets for round robin matches for tournament of size
    `n` and `n+1`, to test both even and odd cases
    """
    DEFAULT_TEAMS = 8
    BYE = "-bye-"

    num_teams = kwargs.get('teams') or DEFAULT_TEAMS

    tourney_a_teams = [f"Team {i + 1}" for i in range(num_teams)]
    tourney_b_teams = [f"Team {i + 1}" for i in range(num_teams + 1)]

    def p(t: TO) -> str:
        return str(t or BYE)

    print(f"Tournament A - {num_teams} Teams")
    for i, matchups in enumerate(RoundRobin.get_matchups(tourney_a_teams)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):8s} vs. {p(matchup[1]):8s}")

    print(f"\nTournament B - {num_teams + 1} Teams")
    for i, matchups in enumerate(RoundRobin.get_matchups(tourney_b_teams)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):8s} vs. {p(matchup[1]):8s}")

    return 0

def run_tournament(*args, **kwargs) -> int:
    """
    """
    if len(args) < 1:
        raise RuntimeError("Tournament name not specified")
    tourn_name = args[0]
    tourn_keys = ('match_games', 'passes', 'elo_update', 'reset_elo')
    tourn_args = {k: kwargs.get(k) for k in tourn_keys if kwargs.get(k) is not None}
    stats_file = kwargs.get('stats_file')
    elo_file   = kwargs.get('elo_file')
    rand_seed  = kwargs.get('rand_seed')  # for system PRNG (`random` module)
    card_seed  = kwargs.get('card_seed')  # for `card` module-specific PRNG
    verbose    = kwargs.get('verbose') or 0
    seeding    = kwargs.get('seeding')

    if rand_seed:
        random.seed(rand_seed)
    if card_seed:
        set_card_seed(card_seed)
    if seeding:
        print("----- Seeding -----")
        # REVISIT: for now, pass same args into both seeding "round"
        # and main tournament, though we may want to put more control
        # and/or integrity around this if becoming a primary interface
        seed_round = Tournament.new(seeding, **tourn_args)
        seed_round.play()
        seed_round.print(verbose=verbose)
        # note that the seeding round results determine the teams playing
        # in the main tournament (even if not matching configured list)
        teams = {name: seed_round.teams[name] for name in seed_round.results}
        tourn_args['teams'] = teams
        tourn_args['seeded'] = True
        tourn_args['reset_elo'] = False
        print("----- Main Tournament -----")
    if profiler:
        profiler.start()
    tourney = Tournament.new(tourn_name, **tourn_args)
    tourney.play()
    if profiler:
        profiler.stop()
        profiler.print()
        #profiler.open_in_browser()
    tourney.print(verbose=verbose)
    if stats_file:
        with open(DataFile(stats_file), 'w', newline='') as file:
            header = tourney.stats_header()
            writer = csv.DictWriter(file, fieldnames=header, dialect='excel-tab',
                                    lineterminator=os.linesep)
            writer.writeheader()
            for row in tourney.iter_stats():
                writer.writerow(row)
    if elo_file:
        with open(DataFile(elo_file), 'w', newline='') as file:
            header = tourney.elo_rating.elo_header()
            writer = csv.DictWriter(file, fieldnames=header, dialect='excel-tab',
                                    lineterminator=os.linesep)
            writer.writeheader()
            for row in tourney.elo_rating.iter_elo():
                writer.writerow(row)

    return 0

def main() -> int:
    """Built-in driver to invoke various utility functions for the module

    Usage: tournament.py <func_name> [<args> ...]

    Functions/usage:

    - round_robin_bracket [teams=<num_teams>]
    - run_tournament <name> [match_games=<int>] [passes=<int>] [stats_file=<stats_file>]
          [reset_elo=<bool>] [elo_update=<tourn_unit>] [elo_file=<elo_file>]
          [rand_seed=<int>] [card_seed=<int>] [verbose=<level>] [seeding=<seed_tourn_name>]
    """
    if len(sys.argv) < 2:
        print(f"Utility function not specified", file=sys.stderr)
        return -1
    elif sys.argv[1] not in globals():
        print(f"Unknown utility function '{sys.argv[1]}'", file=sys.stderr)
        return -1

    util_func = globals()[sys.argv[1]]
    args, kwargs = parse_argv(sys.argv[2:])

    return util_func(*args, **kwargs)

if __name__ == '__main__':
    sys.exit(main())
