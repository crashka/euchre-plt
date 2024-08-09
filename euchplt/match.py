#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from itertools import chain
from collections.abc import Iterator, Iterable
from typing import TextIO

from .core import DEBUG, LogicError
from .team import Team
from .game import GameStat, POS_STATS, Game, NUM_TEAMS

#############
# MatchStat #
#############

# this is a workaround for the fact that Enums are not extendable; note that we create
# our own iterator, since `for stat in MatchStat` will not work

class MatchStatXtra(Enum):
    GAMES_PLAYED = "Games Played"
    GAMES_WON    = "Games Won"

    def __str__(self):
        return self.value

MatchStat = MatchStatXtra | GameStat
def MatchStatIter() -> Iterator: return chain(MatchStatXtra, GameStat)

#########
# Match #
#########

DFLT_MATCH_GAMES = 2

class Match(object):
    """
    """
    # params/config
    teams:       list[Team]
    match_games: int

    # state
    games:     list[Game]                  # sequential
    score:     list[int]                   # (games) indexed as `teams`
    stats:     list[dict[MatchStat, int]]  # each stat indexed as `teams`
    pos_stats: list[dict[MatchStat, list[int]]]  # tabulate stats by call_pos
    winner:    tuple[int, Team] | None     # tuple(idx, team)

    def __init__(self, teams: Iterable[Team], **kwargs):
        """
        """
        self.teams = list(teams)
        if len(self.teams) != NUM_TEAMS:
            raise LogicError(f"Expected {NUM_TEAMS} teams, got {len(self.teams)}")
        self.match_games = kwargs.get('match_games') or DFLT_MATCH_GAMES

        self.games     = []
        self.score     = [0] * NUM_TEAMS
        self.stats     = [{stat: 0 for stat in MatchStatIter()} for _ in self.teams]
        self.pos_stats = [{stat: [0] * 8 for stat in POS_STATS} for _ in self.teams]
        self.winner    = None

    def tabulate(self, game: Game) -> None:
        """
        """
        for i, team in enumerate(self.teams):
            self.stats[i][MatchStatXtra.GAMES_PLAYED] += 1
            if i == game.winner[0]:
                self.score[i] += 1
                self.stats[i][MatchStatXtra.GAMES_WON] += 1

            for stat in GameStat:
                self.stats[i][stat] += game.stats[i][stat]
                if stat in POS_STATS:
                    my_stat_list = self.pos_stats[i][stat]
                    game_stat_list = game.pos_stats[i][stat]
                    for j in range(8):
                        my_stat_list[j] += game_stat_list[j]

    def set_winner(self) -> None:
        """
        """
        winner = None
        for i, team_score in enumerate(self.score):
            if team_score >= self.match_games:
                winner = i, self.teams[i]
                break
        if not winner:
            raise LogicError("Winner not found")
        self.winner = winner

    def play(self) -> None:
        """Play a sequence of games until ``self.match_games`` is reached by one team; we
        are currently re-flipping for dealer for each game (is this the right thing to
        do???)

        Note that the ``Game`` constructor supports specifying the index of the dealer, in
        case we wanted to continue the deal sequence between games (i.e. we would pass in
        the previous ``game.dealer``)

        """
        while max(self.score) < self.match_games:
            game = Game(self.teams)
            self.games.append(game)
            game.play()
            self.tabulate(game)

        self.set_winner()

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """Setting the `verbose` flag (or DEBUG mode) will print out details
        for individual games, as well as printing match stats
        """
        verbose = max(verbose, DEBUG)

        print("Teams:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team}", file=file)
            for j, player in enumerate(team.players):
                print(f"    {player}", file=file)

        if verbose:
            for i, game in enumerate(self.games):
                print(f"Game #{i + 1}:", file=file)
                if verbose > 1:
                    game.print(file=file)
                else:
                    game.print_score(file=file)

        self.print_score(file=file)
        if verbose:
            self.print_stats(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Match Score:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team.name}: {self.score[i]}", file=file)

        if not self.winner:
            return

        print(f"Match Winner:\n  {self.winner[1]}")

    def print_stats(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Match Stats:", file=file)
        for i, team in enumerate(self.teams):
            mystats = self.stats[i]
            print(f"  {team.name}:", file=file)
            for stat in MatchStatIter():
                print(f"    {stat.value + ':':24} {mystats[stat]:8}", file=file)

########
# main #
########

def main() -> int:
    """Built-in driver to run through a simple/sample match
    """
    teams = [Team("Simple Team 1"),
             Team("Smart Team 1")]

    match = Match(teams)
    match.play()
    match.print(verbose=1)

    return 0

if __name__ == '__main__':
    sys.exit(main())
