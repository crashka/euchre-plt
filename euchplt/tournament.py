#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from itertools import chain
from collections.abc import Mapping, Iterator, Iterable
from typing import Optional, Union, TypeVar, TextIO
from numbers import Number
import random
import csv

from .core import DEBUG, cfg, ConfigError
from .team import Team
from .game import GameStat, POS_STATS
from .match import MatchStatXtra, MatchStatIter, Match
from .elo_rating import EloRating

"""
Formats:
  - Head-to-head
  - Round robin
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
"""

######################
# TournStat/CompStat #
######################

# do the same as for `MatchStat` (see match.py)

class TournStatXtra(Enum):
    MATCHES_PLAYED = "Matches Played"
    MATCHES_WON    = "Matches Won"

    def __str__(self):
        return self.value

TournStat = Union[TournStatXtra, MatchStatXtra, GameStat]
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

AllStat = Union[TournStatXtra, MatchStatXtra, GameStat, CompStat]
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

##############
# Tournament #
##############

TeamScores = dict[str, list[Number]]   # [matches, elo_points]
ScoreItem  = tuple[str, list[Number]]  # TeamScores.items()

# superset of tournament subdivisions that subclasses may coopt for
# their own usage/interpretation (other than `MATCH`, of course)
TournUnit = Enum('TournUnit', 'MATCH ROUND PASS')

class Tournament:
    # params/config
    name:           str
    teams:          dict[str, Team]  # indexed by team name
    match_games:    Optional[int]    # num games needed to win match
    # NOTE the different naming convention for position-related stats
    # stuff here, compared to Game and Match classes (should probably
    # make it all consistent at some point)!!!
    pos_stats:      set[GameStat]
    pos_comp_stats: set[CompStat]

    # state, etc.
    # NOTE: matches are appended by `play_match()`, but the parent class has
    # no additional interest in this list; it is up to subclasses to figure
    # out how/whether they want to use it for reporting, analysis, etc.
    matches:        list[Match]
    team_score:     TeamScores             # indexed as `teams`
    team_score_opp: dict[str, TeamScores]  # same as previous, per opponent team
    team_stats:     dict[str, dict[TournStat, int]]  # indexed as `teams`
    team_pos_stats: dict[str, dict[TournStat, list[int]]]  # tabulate stats by call_pos
    winner:         Optional[tuple[Team, ...]]

    @classmethod
    def new(cls, tourn_name: str, **kwargs) -> 'Tournament':
        """Return instantiated Tournament object based on name; format and teams
        are specified in the config file
        """
        tournaments = cfg.config('tournaments')
        if tourn_name not in tournaments:
            raise RuntimeError(f"Tournament '{tourn_name}' is not known")
        tourn_info   = tournaments[tourn_name]
        teams        = tourn_info.get('teams')
        class_name   = tourn_info.get('tourn_class')
        tourn_params = tourn_info.get('tourn_params') or {}
        if not class_name:
            raise ConfigError(f"'tourn_class' not specified for tournament '{tourn_name}'")
        tourn_class = globals()[class_name]
        if not issubclass(tourn_class, cls):
            raise ConfigError(f"'{tourn_class.__name__}' not subclass of '{cls.__name__}'")

        tourn_params.update(kwargs)
        return tourn_class(tourn_name, teams, **tourn_params)

    def __init__(self, name: str, teams: Iterable[Union[str, Team]], **kwargs):
        """Abstract base class, cannot be instantiated directly.  Tournament teams can
        either be specified by name (in the config file) or instantiated `Team` objects
        (format must be consistent within the iterable).
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

        self.matches        = []
        self.team_score     = {name: [0, 0.0] for name in teams}
        self.team_score_opp = {name: {opp: [0, 0.0] for opp in teams if opp is not name}
                               for name in teams}
        self.team_stats     = {name: {stat: 0 for stat in TournStatIter()} for name in teams}
        self.team_pos_stats = {name: {stat: [0] * 8 for stat in self.pos_stats} for name in teams}
        self.winner         = None

    def tabulate(self, match: Match) -> None:
        """Tabulate the result of a single match.  Subclasses may choose to implement and
        invoke additional methods for tabulating after completing rounds, stages, or any
        other subdivision for the specific format.
        """
        for i, team in enumerate(match.teams):
            opp = match.teams[i ^ 0x01]
            self.team_stats[team.name][TS.MATCHES_PLAYED] += 1
            self.team_score[team.name][1] += match.score[i] / sum(match.score)
            self.team_score_opp[team.name][opp.name][1] += match.score[i] / sum(match.score)
            if team == match.winner[1]:
                self.team_stats[team.name][TS.MATCHES_WON] += 1
                self.team_score[team.name][0] += 1
                self.team_score_opp[team.name][opp.name][0] += 1

            for stat in MatchStatIter():
                self.team_stats[team.name][stat] += match.stats[i][stat]
                if stat in self.pos_stats:
                    my_stat_list = self.team_pos_stats[team.name][stat]
                    match_stat_list = match.pos_stats[i][stat]
                    for j in range(8):
                        my_stat_list[j] += match_stat_list[j]

    def set_winner(self) -> None:
        thresh = 0.1  # for floating point comparison
        # determine winner by number of matches won (element score_item[1][0])
        scores = sorted(self.team_score.items(), key=lambda s: s[1][0], reverse=True)
        top_score_item = scores[0]
        winners: list[Team] = [self.teams[top_score_item[0]]]
        for score_item in scores[1:]:
            if top_score_item[1][0] - score_item[1][0] > thresh:
                break
            winners.append(self.teams[score_item[0]])

        self.winner = tuple(winners)

    def play_match(self, matchup: Iterable[Team]) -> None:
        """Uniform/common method for conducting a match within the tournament
        """
        match = Match(matchup, match_games=self.match_games)
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

    def print_score(self, file: TextIO = sys.stdout, vs_opp: bool = False) -> None:
        """Include record against all other teams, if `vs_opp` is specified
        """
        print("Tournament Score:", file=file)
        for name, score in self.team_score.items():
            print(f"  {name}: {score[0]} ({score[1]:.2f})", file=file)
            if vs_opp:
                for opp_name, score in self.team_score_opp[name].items():
                    opp_score = self.team_score_opp[opp_name][name]
                    print(f"    vs {opp_name}: {score[0]} - {opp_score[0]} "
                          f"({score[1]:.2f} - {opp_score[1]:.2f})", file=file)

        if not self.winner:
            return

        plural = "s" if len(self.winner) > 1 else ""
        winner_names = (t.name for t in self.winner)
        print(f"Tournament Winner{plural}:\n  {', '.join(winner_names)}")

    def print_stats(self, file: TextIO = sys.stdout, by_pos: bool = False) -> None:
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
# RoundRobin #
##############

DFLT_PASSES     = 1
DFLT_ELO_UPDATE = 'PASS'

T = TypeVar('T')
TO = Optional[T]

class RoundRobin(Tournament):
    """This is a modified round robin format wherein multiple passes through the
    field is supported.  In addition, the lowest ranked teams may be eliminated
    after each `elim_passes` cycle, if specified.  Note that `elim_pct` is
    computed relative to the original field size, so the number of teams
    eliminated each cycle is always the same.
    """
    # params
    passes:       int
    elim_passes:  int
    elim_pct:     int
    reset_elo:    bool
    elo_update:   TournUnit
    elo_params:   dict[str, Union[str, Number]]
    elo_rating:   EloRating

    # state, etc.
    elim_num:     int        # number to eliminate per cycle
    eliminated:   set[Team]  # set of team names
    leaderboards: list[list[ScoreItem]]  # for each pass, sorted by descending score

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

    def __init__(self, name: str, teams: Union[Iterable[str], Iterable[Team]], **kwargs):
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
        self.eliminated = set()
        self.leaderboards = []

    def tabulate(self, match: Match) -> None:
        super().tabulate(match)
        if self.elo_update == TournUnit.MATCH:
            self.elo_rating.update([match])

    def tabulate_round(self, round_num: int, matches: list[Match]) -> None:
        """For now, we don't do anything here--since every teams plays at most
        once per round, this is the same as per-match tabulation
        """
        if self.elo_update == TournUnit.ROUND:
            self.elo_rating.update(matches, collective=True)

    def tabulate_pass(self, pass_num: int, matches: list[Match]) -> None:
        """Do collective Elo ratings updates, if requested (otherwise nothing else to
        do, currently)
        """
        if self.elo_update == TournUnit.PASS:
            self.elo_rating.update(matches, collective=True)

        num_passes = pass_num + 1
        leaderboard = sorted(self.team_score.items(), key=lambda s: s[1][0], reverse=True)
        self.leaderboards.append(leaderboard)
        self.print_leaderboard(f"pass {pass_num}")

        if self.elim_passes and num_passes % self.elim_passes == 0:
            # don't go below `elim_pct` teams remaining
            if len(self.teams) - len(self.eliminated) >= self.elim_num * 2:
                leader_teams = [self.teams[s[0]] for s in leaderboard
                                if self.teams[s[0]] not in self.eliminated]
                self.eliminated.update(leader_teams[-self.elim_num:])
        self.matches.clear()

    def set_winner(self) -> None:
        super().set_winner()
        self.elo_rating.persist(archive=True)

    def play(self, **kwargs) -> None:
        """Perform configured number of passes for the tournament, where a pass is
        a single round robin.  We do pass-level progress reporting before truncating
        `self.matches` to avoid infinite memory consumption.
        """
        for pass_num in range(self.passes):
            pass_start = len(self.matches)
            active_teams = set(self.teams.values()) - self.eliminated
            for round_num, matchups in enumerate(self.get_matchups(active_teams)):
                round_start = len(self.matches)
                for matchup in matchups:
                    if None in matchup:
                        continue
                    self.play_match(matchup)  # note this invokes `tabulate()`
                self.tabulate_round(round_num, self.matches[round_start:])
            self.tabulate_pass(pass_num, self.matches[pass_start:])
        self.set_winner()

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        super().print(file, verbose)
        self.elo_rating.print(file=file, verbose=verbose)

    def print_leaderboard(self, label: str = None, file: TextIO = sys.stdout):
        label_str = f" ({label})" if label else ""
        print(f"Leaderboard{label_str}:")
        for name, score in self.leaderboards[-1]:
            active  = '' if self.teams[name] in self.eliminated else '*'
            losses  = self.team_stats[name][TS.MATCHES_PLAYED] - score[0]
            cur_elo = self.elo_rating.team_ratings[name]
            print(f"  {name}{active}\t{score[0]}-{losses}\t{score[1]:.2f}\t{cur_elo:.1f}", file=file)

##############
# HeadToHead #
##############

class HeadToHead(Tournament):
    pass

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
    if len(args) < 1:
        raise RuntimeError("Tournament name not specified")
    tourn_name = args[0]
    tourn_keys = ('match_games', 'passes', 'elo_update', 'reset_elo')
    tourn_args = {k: kwargs.get(k) for k in tourn_keys if kwargs.get(k) is not None}
    stats_file = kwargs.get('stats_file')
    elo_file   = kwargs.get('elo_file')
    seed       = kwargs.get('seed')
    verbose    = kwargs.get('verbose') or 0

    if seed:
        random.seed(seed)
    tourney = Tournament.new(tourn_name, **tourn_args)
    tourney.play()
    tourney.print(verbose=verbose)
    if stats_file:
        with open(stats_file, 'w', newline='') as file:
            header = tourney.stats_header()
            writer = csv.DictWriter(file, fieldnames=header, dialect='excel-tab')
            writer.writeheader()
            for row in tourney.iter_stats():
                writer.writerow(row)
    if elo_file:
        with open(elo_file, 'w', newline='') as file:
            header = tourney.elo_rating.elo_header()
            writer = csv.DictWriter(file, fieldnames=header, dialect='excel-tab')
            writer.writeheader()
            for row in tourney.elo_rating.iter_elo():
                writer.writerow(row)

    return 0

def main() -> int:
    """Built-in driver to invoke various utility functions for the module

    Usage: strategy.py <func_name> [<args> ...]

    Functions/usage:
      - round_robin_bracket [teams=<num_teams>]
      - run_tournament <name> [match_games=<n_games>] [passes=<passes>] [stats_file=<stats_file>]
                       [reset_elo=<bool>] [elo_update=<tourn_unit>] [elo_file=<elo_file>]
                       [seed=<rand_seed>] [verbose=<level>]
    """
    if len(sys.argv) < 2:
        print(f"Utility function not specified", file=sys.stderr)
        return -1
    elif sys.argv[1] not in globals():
        print(f"Unknown utility function '{sys.argv[1]}'", file=sys.stderr)
        return -1
    util_func = globals()[sys.argv[1]]

    def typecast(val: str) -> Union[str, Number, bool]:
        if val.isdecimal():
            return int(val)
        if val.isnumeric():
            return float(val)
        if val.lower() in ['false', 'f', 'no', 'n']:
            return False
        if val.lower() in ['true', 't', 'yes', 'y']:
            return True
        if val.lower() in ['null', 'none', 'nil']:
            return None
        return val if len(val) > 0 else None

    args = []
    kwargs = {}
    args_done = False
    for arg in sys.argv[2:]:
        if not args_done:
            if '=' not in arg:
                args.append(typecast(arg))
                continue
            else:
                args_done = True
        kw, val = arg.split('=', 1)
        kwargs[kw] = typecast(val)

    return util_func(*args, **kwargs)

if __name__ == '__main__':
    sys.exit(main())
