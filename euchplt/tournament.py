#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from itertools import chain
from collections.abc import Mapping, Iterator, Iterable
from typing import Optional, Union, TypeVar, TextIO
from numbers import Number
import random
import shelve
import csv

from .core import DEBUG, cfg, ConfigError, DataFile, ArchiveDataFile
from .team import Team
from .game import GameStat, POS_STATS
from .match import MatchStatXtra, MatchStatIter, Match

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

###############
# elo ratings #
###############

DFLT_ELO_DB      = 'elo_rating.db'
DFLT_INIT_RATING = 1500.0
DFLT_D_VALUE     = 400
DFLT_K_FACTOR    = 24

class EloRating:
    """Elo ratings are currently persisted using `shelve`, see caveats below.
    """
    elo_db:       str
    init_rating:  float
    d_value:      int
    k_factor:     int
    team_ratings: dict[str, float]        # indexed by team name
    ratings_hist: dict[str, list[float]]  # list of updates, indexed by team name

    def __init__(self, teams: Iterable[Team], params: dict = None):
        params = params or {}
        self.elo_db        = params.get('elo_db')        or DFLT_ELO_DB
        self.reset_ratings = params.get('reset_ratings') or False
        self.init_rating   = params.get('init_rating')   or DFLT_INIT_RATING
        self.d_value       = params.get('d_value')       or DFLT_D_VALUE
        self.k_factor      = params.get('k_factor')      or DFLT_K_FACTOR

        if self.reset_ratings:
            self.team_ratings = {t.name: self.init_rating for t in teams}
        else:
            self.team_ratings = self.load(teams)
        # seed history with initial ratings
        self.ratings_hist = {t.name: [self.team_ratings[t.name]] for t in teams}

    def load(self, teams: Optional[Iterable[Team]] = None) -> dict[str, float]:
        """Loads Elo ratings from the database; return ratings for specified teams
        only (initializing them, if not yet existing), or the entire database (with
        no initializations) if `teams` is not passed in.

        CAVEAT: there is currently no locking or integrity mechanisms for the
        database, so conflicts can happen if concurrently accessed!!!
        """
        with shelve.open(DataFile(self.elo_db)) as db:
            if teams:
                team_elo = {t.name: db.get(t.name) or self.init_rating for t in teams}
            else:
                team_elo = {k: v for k, v in db.items()}
        return team_elo

    def get(self, team: Team) -> tuple[float, list[float]]:
        """Returns tuple of current rating and list of rating history (i.e. all of
        the updates for the current instantiation) for `team`
        """
        return self.team_ratings[team.name], self.ratings_hist[team.name]

    def update(self, matches: Iterable[Match], collective: bool = False) -> None:
        """Recomputes Elo ratings for teams participating in `matches`; does not
        affect the rating for any teams not specified.  Note that these updates
        are not persisted until `persist()` is called.
        """
        if collective:
            return self._update_collective(matches)
        # The remainder of this method computes new Elo ratings on a sequential
        # per-match basis.  This does the right thing within a tournament round
        # where individual teams will only play once, otherwise the "collective"
        # alternative should be considered
        for match in matches:
            r = []  # inbound rating
            q = []
            e = []  # expected score
            s = []  # actual score
            for i, team in enumerate(match.teams):
                r.append(self.team_ratings[team.name])
                q.append(pow(10.0, r[i] / self.d_value))
            # loop again, since we need complete `q`
            for i, team in enumerate(match.teams):
                e.append(q[i] / sum(q))
                s.append(match.score[i] / sum(match.score))
                r_delta = self.k_factor * (s[i] - e[i])
                self.team_ratings[team.name] += r_delta
                self.ratings_hist[team.name].append(self.team_ratings[team.name])

    def _update_collective(self, matches: Iterable[Match]) -> None:
        """We sum the inbound ratings and scores, and do single bulk computations
        for some segment of the tournament in which inbound ratings are fixed.
        """
        e = {name: 0.0 for name in self.team_ratings}  # sum of expected scores
        s = {name: 0.0 for name in self.team_ratings}  # sum of actual scores
        for match in matches:
            r = []  # inbound rating
            q = []
            for i, team in enumerate(match.teams):
                r.append(self.team_ratings[team.name])
                q.append(pow(10.0, r[i] / self.d_value))
            # loop again, since we need complete `q`
            for i, team in enumerate(match.teams):
                e[team.name] += q[i] / sum(q)
                s[team.name] += match.score[i] / sum(match.score)

        for name in self.team_ratings:
            r_delta = self.k_factor * (s[name] - e[name])
            self.team_ratings[name] += r_delta
            self.ratings_hist[name].append(self.team_ratings[name])

    def persist(self, archive: bool = False) -> None:
        """Merges current Elo ratings with the existing database; the previous
        version may be archived, if requested.  See CAVEAT in `load()` regarding
        database integrity--note that there is an additional race condition here
        in the archiving of the database file.
        """
        ratings_db = self.load()
        ratings_db.update(self.team_ratings)
        if archive:
            ArchiveDataFile(DataFile(self.elo_db))
        with shelve.open(DataFile(self.elo_db), flag='c') as db:
            for key, rating in ratings_db.items():
                db[key] = rating

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """Print Elo history, if `verbose` specified
        """
        verbose = max(verbose, DEBUG)

        print("Elo Ratings:", file=file)
        for name, cur_rating in self.team_ratings.items():
            if verbose > 1:
                hist = self.ratings_hist[name]
                hist_str = " [" + ', '.join([f"{rating:.1f}" for rating in hist]) + "]"
            else:
                hist_str = ""
            print(f"  {name}: {cur_rating:6.1f}{hist_str}", file=file)

    def elo_header(self) -> list[str]:
        """Header fields corresponding to the keys for `iter_elo()` yield
        """
        TEAM_COL = 'Team'
        arb_name = next(iter(self.ratings_hist))
        arb_hist = self.ratings_hist[arb_name]
        fields = [TEAM_COL] + [f"Elo {i}" for i in range(len(arb_hist))]
        return fields

    def iter_elo(self) -> dict[str, Number]:
        """Ratings history data corresponding to the fields returned by `elo_header()`
        """
        TEAM_COL = 'Team'
        for name, ratings in self.ratings_hist.items():
            team_hist = {f"Elo {i}": val for i, val in enumerate(ratings)}
            hist_row = {TEAM_COL: name} | team_hist
            yield hist_row

##############
# Tournament #
##############

class Tournament:
    name:           str
    teams:          dict[str, Team]                  # indexed by team name
    # NOTE the different naming convention for position-related stats
    # stuff here, compared to Game and Match classes (should probably
    # make it all consistent at some point)!!!
    pos_stats:      set[GameStat]
    pos_comp_stats: set[CompStat]
    matches:        list[Match]                      # sequential
    team_matches:   dict[str, list[Match]]           # indexed as `teams`
    team_score:     dict[str, list[Number]]          # [matches, elo_points], indexed as `teams`
    team_stats:     dict[str, dict[TournStat, int]]  # indexed as `teams`
    team_pos_stats: dict[str, dict[TournStat, list[int]]]   # tabulate stats by call_pos
    winner:         Optional[tuple[Team, ...]]
    elo_rating:     EloRating

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
        pos_stats           = kwargs.get('pos_stats') or []
        pos_comp_stats      = kwargs.get('pos_comp_stats') or []
        elo_params          = kwargs.get('elo_rating') or {}

        self.pos_stats      = set(GameStat[s.upper()] for s in pos_stats)
        self.pos_comp_stats = set(CompStat[s.upper()] for s in pos_comp_stats)
        for stat in self.pos_comp_stats:
            if set(CompStatFormulas[stat]) - self.pos_stats:
                raise ConfigError(f"Stat '{stat.name}' has missing dependencies in 'pos_stats'")

        self.matches        = []
        self.team_matches   = {name: [] for name in self.teams}
        self.team_score     = {name: [0, 0.0] for name in teams}
        self.team_stats     = {name: {stat: 0 for stat in TournStatIter()} for name in teams}
        self.team_pos_stats = {name: {stat: [0] * 8 for stat in self.pos_stats} for name in teams}
        self.winner         = None
        self.elo_rating     = EloRating(self.teams.values(), elo_params)

    def tabulate(self, match: Match, update_elo: bool = True) -> None:
        """Tabulate the result of a single match.  Subclasses may choose to implement and
        invoke additional methods for tabulating after completing rounds, stages, or any
        other subdivision for the specific format.

        Note that `update_elo` may be specified as False so that "collective" Elo ratings
        may be computed (must be managed by the subclass, for now)
        """
        for i, team in enumerate(match.teams):
            self.team_stats[team.name][TournStatXtra.MATCHES_PLAYED] += 1
            self.team_score[team.name][1] += match.score[i] / sum(match.score)
            if team == match.winner[1]:
                self.team_stats[team.name][TournStatXtra.MATCHES_WON] += 1
                self.team_score[team.name][0] += 1

            for stat in MatchStatIter():
                self.team_stats[team.name][stat] += match.stats[i][stat]
                if stat in self.pos_stats:
                    my_stat_list = self.team_pos_stats[team.name][stat]
                    match_stat_list = match.pos_stats[i][stat]
                    for j in range(8):
                        my_stat_list[j] += match_stat_list[j]

        if update_elo:
            self.elo_rating.update([match])

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
        self.elo_rating.persist(archive=True)

    def play_match(self, matchup: Iterable[Team], update_elo: bool = True) -> None:
        """Uniform/common method for conducting a match within the tournament

        REVISIT: it's kind of ugly to take `update_elo` as an arg and just
        pass it along, but `tabulate()` needs it (see above) and really does
        belong with in this sequence [or not???]
        """
        match = Match(matchup)
        self.matches.append(match)
        match.play()
        self.tabulate(match, update_elo=update_elo)

    def play(self, **kwargs) -> None:
        """Abstract method to be implemented by all subclasses, who should
        then invoke `play_match()` to conduct each of the matchups created
        for the tournament type
        """
        raise NotImplementedError("Can't call abstract method")

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        verbose = max(verbose, DEBUG)

        if verbose:
            print("Teams:", file=file)
            for i, team in enumerate(self.teams.values()):
                print(f"  {team}", file=file)
                for j, player in enumerate(team.players):
                    print(f"    {player}", file=file)

            for i, match in enumerate(self.matches):
                print(f"Match #{i + 1}:", file=file)
                match.print_score(file=file)

        self.print_score(file=file)
        if verbose:
            self.print_stats(file=file, by_pos=(verbose > 0))
            self.elo_rating.print(file=file, verbose=verbose)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        print("Tournament Score:", file=file)
        for name in self.teams:
            print(f"  {name}: {self.team_score[name][0]} "
                  f"({self.team_score[name][1]:.2f})", file=file)

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

DFLT_PASSES  = 1
DFLT_ELO_INT = 'PASS'

EloInt = Enum('EloInt', 'MATCH ROUND PASS')

T = TypeVar('T')
TO = Optional[T]

class RoundRobin(Tournament):
    passes:  int
    elo_int: EloInt

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
        self.passes  = kwargs.get('passes') or DFLT_PASSES
        elo_int_str  = kwargs.get('elo_int') or DFLT_ELO_INT
        self.elo_int = EloInt[elo_int_str.upper()]

    def tabulate_round(self, matches: list[Match], update_elo: bool = False) -> None:
        """For now, we don't do anything here--since every teams plays at most
        once per round, this is the same as per-match tabulation
        """
        if update_elo:
            self.elo_rating.update(matches, collective=True)

    def tabulate_pass(self, matches: list[Match], update_elo: bool = False) -> None:
        """Do collective Elo ratings updates, if requested (otherwise nothing else to
        do, currently)
        """
        if update_elo:
            self.elo_rating.update(matches, collective=True)

    def play(self, **kwargs) -> None:
        int_match = self.elo_int == EloInt.MATCH
        int_round = self.elo_int == EloInt.ROUND
        int_pass  = self.elo_int == EloInt.PASS

        match_num = 0  # corresponds to index within `self.matches`
        for pass_num in range(self.passes):
            pass_start = match_num
            for round_num, matchups in enumerate(self.get_matchups(self.teams.values())):
                round_start = match_num
                for matchup in matchups:
                    if None in matchup:
                        continue
                    self.play_match(matchup, update_elo=int_match)
                    match_num += 1
                self.tabulate_round(self.matches[round_start:], update_elo=int_round)
            self.tabulate_pass(self.matches[pass_start:], update_elo=int_pass)

        self.set_winner()

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
    tourn_keys = ('passes', 'elo_int')
    tourn_args = {k: kwargs.get(k) for k in tourn_keys if kwargs.get(k)}
    stats_file = kwargs.get('stats_file')
    elo_file   = kwargs.get('elo_file')
    seed       = kwargs.get('seed')

    if seed:
        random.seed(seed)
    tourney = Tournament.new(tourn_name, **tourn_args)
    tourney.play()
    tourney.print(verbose=1)
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
      - run_tournament <name> [passes=<passes>] [elo_int=<elo_int>] [stats_file=<stats_file>]
                       [elo_file=<elo_file>] [seed=<rand_seed>]
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
