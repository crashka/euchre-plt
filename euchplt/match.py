#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from typing import Optional, Iterable, TextIO

from .core import LogicError
from .player import Player
from .team import Team
from .game import Game, NUM_TEAMS, GAME_POINTS

VERBOSE = False  # TEMP!!!

#############
# MatchStat #
#############

class MatchStat(Enum):
    GAMES   = "Games"
    TRICKS  = "Tricks"
    POINTS  = "Points"
    MAKES   = "Makes"
    LONERS  = "Loners"
    EUCHRES = "Euchres"

#########
# Match #
#########

MATCH_GAMES = 2

class Match(object):
    """
    """
    teams:  list[Team]
    games:  list[Game]                  # sequential
    score:  list[int]                   # (games) indexed as `teams`
    stats:  dict[MatchStat, list[int]]  # each stat indexed as `teams`
    winner: Optional[Team]

    def __init__(self, teams: Iterable[Team]):
        """
        """
        self.teams = list(teams)
        if len(self.teams) != NUM_TEAMS:
            raise LogicError(f"Expected {NUM_TEAMS} teams, got {len(self.teams)}")
        self.games  = []
        self.score  = [0] * NUM_TEAMS
        self.stats  = {stat: [0] * NUM_TEAMS for stat in MatchStat}
        self.winner = None

    def tabulate(self, game: Game) -> None:
        """
        """
        for i, team in enumerate(self.teams):
            self.score[i] += int(game.score[i] >= GAME_POINTS)

    def set_winner(self) -> None:
        """
        """
        winner = None
        for i, team_score in enumerate(self.score):
            if team_score >= MATCH_GAMES:
                winner = self.teams[i]
                break
        if not winner:
            raise LogicError("Winner not found")
        self.winner = winner

    def play(self) -> None:
        """
        """
        while max(self.score) < MATCH_GAMES:
            game = Game(self.teams)
            self.games.append(game)
            game.play()
            self.tabulate(game)

        self.set_winner()

    def print(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Teams:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team}", file=file)
            for j, player in enumerate(team.players):
                print(f"    {player}", file=file)

        for i, game in enumerate(self.games):
            print(f"Game #{i + 1}:", file=file)
            if VERBOSE:
                game.print(file=file)
            else:
                game.print_score(file=file)

        self.print_score(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        print("Match Score:", file=file)
        for j, team in enumerate(self.teams):
            print(f"  {team.name}: {self.score[j]}", file=file)

        if not self.winner:
            return

        print(f"Match Winner:\n  {self.winner}")

########
# main #
########

from .strategy import StrategySimple

def main() -> int:
    """Built-in driver to run through a simple/sample match
    """
    plyr_params = [{},
                   {'take_high': True},
                   {},
                   {'take_high': True}]
    players     = [Player("Player 0", StrategySimple, **plyr_params[0]),
                   Player("Player 1", StrategySimple, **plyr_params[1]),
                   Player("Player 2", StrategySimple, **plyr_params[2]),
                   Player("Player 3", StrategySimple, **plyr_params[3])]
    teams       = [Team([players[0], players[2]]),
                   Team([players[1], players[3]])]

    match = Match(teams)
    match.play()
    match.print()

    return 0

if __name__ == '__main__':
    sys.exit(main())
