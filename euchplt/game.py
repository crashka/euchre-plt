#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from typing import Optional, Iterable, TextIO
import random

from .core import LogicError
from .card import get_deck
from .deal import DealAttr, Deal, NUM_PLAYERS, BIDDER_POS, DEALER_POS
from .player import Player
from .team import Team

VERBOSE = False  # TEMP!!!

############
# GameStat #
############

class GameStat(Enum):
    DEALS_PLAYED   = "Deals Played"
    DEALS_PASSED   = "Deals Passed"
    TRICKS         = "Tricks"
    POINTS         = "Points"
    MAKES          = "Makes"
    ALL_FIVES      = "All 5's"
    LONERS         = "Loners"
    EUCHRED        = "Euchred"
    LONERS_EUCHRED = "Loners Euchred"
    EUCHRES        = "Euchres"
    EUCHRES_ALONE  = "Euchres Alone"

########
# Game #
########

NUM_TEAMS    = 2
TEAM_PLAYERS = 2
GAME_POINTS  = 10

class Game(object):
    """
    """
    teams:  list[Team]
    deals:  list[Deal]                 # sequential
    score:  list[int]                  # (points) indexed as `teams`
    stats:  list[dict[GameStat, int]]  # each stat indexed as `teams`
    winner: Optional[tuple[int, Team]]

    def __init__(self, teams: Iterable[Team]):
        """
        """
        self.teams = list(teams)
        if len(self.teams) != NUM_TEAMS:
            raise LogicError(f"Expected {NUM_TEAMS} teams, got {len(self.teams)}")
        self.deals  = []
        self.score  = []
        self.stats  = [{stat: 0 for stat in GameStat} for _ in range(NUM_TEAMS)]
        self.winner = None

    def player_team(self, player: Player) -> tuple[int, Team]:
        """
        """
        for i, team in enumerate(self.teams):
            if player in team.players:
                return i, team
        raise LogicError(f"Team not found for player '{player}'")

    def tabulate(self, players: list[Player], deal: Deal) -> None:
        """
        """
        if deal.is_passed():
            for pos in (BIDDER_POS, DEALER_POS):
                team_idx = self.player_team(players[pos])[0]
                stat = self.stats[team_idx]
                stat[GameStat.DEALS_PASSED] += 1
            return

        assert len(deal.points) == len(players)
        assert len(deal.tricks_won) == len(players)

        for pos in (BIDDER_POS, DEALER_POS):
            team_idx = self.player_team(players[pos])[0]
            self.score[team_idx] += deal.points[pos]

            stat = self.stats[team_idx]
            stat[GameStat.DEALS_PLAYED] += 1
            stat[GameStat.TRICKS] += deal.tricks_won[pos]
            stat[GameStat.POINTS] += deal.points[pos]

        call_team_idx = self.player_team(players[deal.caller_pos])[0]
        def_team_idx  = self.player_team(players[deal.caller_pos ^ 0x01])[0]
        call_stat     = self.stats[call_team_idx]
        def_stat      = self.stats[def_team_idx]

        if DealAttr.MAKE in deal.result:
            assert DealAttr.EUCHRE not in deal.result
            call_stat[GameStat.MAKES] += 1
            if DealAttr.ALL_5 in deal.result:
                call_stat[GameStat.ALL_FIVES] += 1
                if DealAttr.GO_ALONE in deal.result:
                    call_stat[GameStat.LONERS] += 1
        else:
            assert DealAttr.EUCHRE in deal.result
            call_stat[GameStat.EUCHRED] += 1
            if DealAttr.GO_ALONE in deal.result:
                call_stat[GameStat.LONERS_EUCHRED] += 1
            def_stat[GameStat.EUCHRES] += 1
            if DealAttr.DEF_ALONE in deal.result:
                def_stat[GameStat.EUCHRES_ALONE] += 1

    def set_winner(self) -> None:
        """
        """
        winner = None
        for i, team_score in enumerate(self.score):
            if team_score >= GAME_POINTS:
                winner = i, self.teams[i]
                break
        if not winner:
            raise LogicError("Winner not found")
        self.winner = winner

    def play(self) -> None:
        """
        """
        # TODO: randomize seating within teams!!!
        seats = [t.players[n] for n in range(TEAM_PLAYERS) for t in self.teams]
        assert len(seats) == NUM_PLAYERS
        dealer_idx = random.randrange(NUM_PLAYERS)  # relative to `seats`

        self.score = [0] * NUM_TEAMS
        while max(self.score) < GAME_POINTS:
            bidder_idx = (dealer_idx + 1) % NUM_PLAYERS
            players = seats[bidder_idx:] + seats[:bidder_idx]
            deck = get_deck()
            deal = Deal(players, deck)
            self.deals.append(deal)

            deal.deal_cards()
            deal.do_bidding()
            if not deal.is_passed():
                deal.play_cards()
            self.tabulate(players, deal)
            dealer_idx = (dealer_idx + 1) % NUM_PLAYERS

        self.set_winner()

    def print(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Teams:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team}", file=file)
            for j, player in enumerate(team.players):
                print(f"    {player}", file=file)

        for i, deal in enumerate(self.deals):
            print(f"Deal #{i + 1}:", file=file)
            if VERBOSE:
                deal.print(file=file)
            else:
                deal.print_score(file=file)

        self.print_score(file=file)
        self.print_stats(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        print("Game Score:", file=file)
        for j, team in enumerate(self.teams):
            print(f"  {team.name}: {self.score[j]}", file=file)

        if not self.winner:
            return

        print(f"Game Winner:\n  {self.winner[1]}")

    def print_stats(self, file: TextIO = sys.stdout) -> None:
        print("Game Stats:", file=file)
        for j, team in enumerate(self.teams):
            print(f"  {team.name}:", file=file)
            for stat in GameStat:
                print(f"    {stat.value + ':':15} {self.stats[j][stat]:4}", file=file)

########
# main #
########

from .strategy import StrategySimple

def main() -> int:
    """Built-in driver to run through a simple/sample game
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

    game = Game(teams)
    game.play()
    game.print()

    return 0

if __name__ == '__main__':
    sys.exit(main())
