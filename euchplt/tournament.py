#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from itertools import chain
from typing import Optional, Union, TypeVar, Iterable, Iterator, TextIO
from numbers import Number

from .core import cfg, ConfigError
from .team import Team
from .game import GameStat
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
  - ELO is computed within (and across?) tournaments
    - Investigate win- and score-based ELO calculations
  - Report cumulative match stats as well
  - OPEN ISSUE: should we assign 'seats' at the match level?
"""

VERBOSE = False  # TEMP!!!

#############
# TournStat #
#############

# do the same as for `MatchStat` (see match.py)

class TournStatXtra(Enum):
    MATCHES_PLAYED = "Matches Played"
    MATCHES_WON    = "Matches Won"

TournStat = Union[TournStatXtra, MatchStatXtra, GameStat]
def TournStatIter() -> Iterator: return chain(TournStatXtra, MatchStatXtra, GameStat)

##############
# Tournament #
##############

def get_tournament(tourn_name: str, **kwargs) -> 'Tournament':
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

    tourn_params.update(kwargs)
    return tourn_class(tourn_name, teams, **tourn_params)

class Tournament:
    name:         str
    teams:        dict[str, Team]                  # indexed by team name
    matches:      list[Match]                      # sequential
    team_matches: dict[str, list[Match]]           # indexed as `teams`
    team_score:   dict[str, list[Number]]          # [matches, elo_points], indexed as `teams`
    team_stats:   dict[str, dict[TournStat, int]]  # indexed as `teams`
    winner:       Optional[tuple[Team, ...]]
    
    def __init__(self, name: str, teams: Iterable[Union[str, Team]]):
        """Abstract base class, cannot be instantiated directly.  Tournament teams can
        either be specified by name (in the config file) or instantiated `Team` objects
        (format must be consistent within the iterable).
        """
        self.name = name
        self.teams = {}
        for idx, team in enumerate(teams):
            if isinstance(team, str):
                team = Team(team)
            self.teams[team.name] = team
        if len(self.teams) < 2:
            raise RuntimeError("At least two teams must be specified")
        if len(self.teams) < idx + 1:
            raise RuntimeError("Team names must be unique")

        self.matches      = []
        self.team_matches = {name: [] for name in self.teams}
        self.team_score   = {name: [0, 0.0] for name in teams}
        self.team_stats   = {name: {stat: 0 for stat in TournStatIter()} for name in teams}
        self.winner       = None

    def tabulate(self, match: Match) -> None:
        for i, team in enumerate(match.teams):
            self.team_stats[team.name][TournStatXtra.MATCHES_PLAYED] += 1
            self.team_score[team.name][1] += match.score[i] / sum(match.score)
            if team == match.winner[1]:
                self.team_stats[team.name][TournStatXtra.MATCHES_WON] += 1
                self.team_score[team.name][0] += 1

            for stat in MatchStatIter():
                self.team_stats[team.name][stat] += match.stats[i][stat]

    def set_winner(self) -> None:
        """
        """
        thresh = 0.1
        # determine winner by number of matches won
        scores = sorted(self.team_score.items(), key=lambda s: s[1][0], reverse=True)
        winners = [self.teams[scores[0][0]]]
        for score_item in scores[1:]:
            if scores[0][1][0] - score_item[1][0] > thresh:
                break
            winners.append(self.teams[score_item[0]])
                
        self.winner = tuple(winners)

    def play(self) -> None:
        raise NotImplementedError("Can't call abstract method")

    def print(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Teams:", file=file)
        for i, team in enumerate(self.teams.values()):
            print(f"  {team}", file=file)
            for j, player in enumerate(team.players):
                print(f"    {player}", file=file)

        for i, match in enumerate(self.matches):
            print(f"Match #{i + 1}:", file=file)
            if VERBOSE:
                match.print(file=file)
            else:
                match.print_score(file=file)

        self.print_score(file=file)
        self.print_stats(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        print("Tournament Score:", file=file)
        for j, team in enumerate(self.teams.values()):
            print(f"  {team.name}: {self.team_score[team.name][0]} "
                  f"({self.team_score[team.name][1]:.2f})", file=file)

        if not self.winner:
            return

        plural = "s" if len(self.winner) > 1 else ""
        winner_names = (t.name for t in self.winner)
        print(f"Tournament Winner{plural}:\n  {', '.join(winner_names)}")

    def print_stats(self, file: TextIO = sys.stdout) -> None:
        print("Tournament Stats:", file=file)
        for j, team in enumerate(self.teams.values()):
            print(f"  {team.name}:", file=file)
            for stat in TournStatIter():
                print(f"    {stat.value + ':':16} {self.team_stats[team.name][stat]:8}", file=file)

##############
# RoundRobin #
##############

DFLT_PASSES = 1

T = TypeVar('T')
TO = Optional[T]

def round_robin_matchups(teams: Iterable[T]) -> Iterator[list[tuple[TO, TO]]]:
    """Note that `None` in a matchup represents a bye
    """
    teams_list = list(teams)
    if len(teams_list) % 2 == 1:
        teams_list.append(None)
    n_teams = len(teams_list)
    n_matchups = n_teams // 2
    list_head = teams_list[:1]
    list_tail = teams_list[1:]

    def rotate(my_list: list[TO], n: int = 1) -> list[TO]:
        return my_list[n:] + my_list[:n]

    def matchups(my_field: list[TO]) -> Iterable[tuple[TO, TO]]:
        home = my_field[:n_matchups]
        away = reversed(my_field[n_matchups:])
        return zip(home, away)

    for _ in range(n_teams - 1):
        field = list_head + list_tail
        yield matchups(field)
        list_tail = rotate(list_tail)

class RoundRobin(Tournament):
    passes: int

    def __init__(self, name: str, teams: Union[Iterable[str], Iterable[Team]], **kwargs):
        super().__init__(name, teams)
        self.passes = kwargs.get('passes') or DFLT_PASSES

    def play(self) -> None:
        """
        """
        for pass_num in range(self.passes):
            for round_num, matchups in enumerate(round_robin_matchups(self.teams.values())):
                for matchup in matchups:
                    match = Match(matchup)
                    match.play()
                    self.tabulate(match)

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

def round_robin_bracket(*args) -> int:
    """Print out brackets for round robin matches for tournament of size
    `n` and `n+1`, to test both even and odd cases
    """
    DEFAULT_TEAMS = 8
    BYE = "-bye-"

    n_teams = int(args[0]) if args else DEFAULT_TEAMS

    tourney_a_teams = [f"Team {i + 1}" for i in range(n_teams)]
    tourney_b_teams = [f"Team {i + 1}" for i in range(n_teams + 1)]

    def p(t: TO) -> str:
        return str(t or BYE)

    print(f"Tournament A - {n_teams} Teams")
    for i, matchups in enumerate(round_robin_matchups(tourney_a_teams)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):8s} vs. {p(matchup[1]):8s}")

    print(f"\nTournament B - {n_teams + 1} Teams")
    for i, matchups in enumerate(round_robin_matchups(tourney_b_teams)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):8s} vs. {p(matchup[1]):8s}")

    return 0

def run_tournament(*args) -> int:
    if len(args) < 1:
        raise RuntimeError("Tournament name not specified")
    if len(args) > 1:
        tourney = get_tournament(args[0], passes=int(args[1]))
    else:
        tourney = get_tournament(args[0])
    tourney.play()
    tourney.print()

    return 0

def main() -> int:
    """Built-in driver to invoke various utility functions for the module

    Usage: strategy.py <func_name> [<arg> ...]

    Functions/usage:
      - round_robin_bracket [<n_teams>]
      - run_tournament [<name> | <team_name> ...]
    """
    if len(sys.argv) < 2:
        print(f"Utility function not specified", file=sys.stderr)
        return -1
    elif sys.argv[1] not in globals():
        print(f"Unknown utility function '{sys.argv[1]}'", file=sys.stderr)
        return -1

    util_func = globals()[sys.argv[1]]
    util_args = sys.argv[2:]
    return util_func(*util_args)

if __name__ == '__main__':
    sys.exit(main())
