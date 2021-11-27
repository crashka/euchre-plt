#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from typing import Optional, Iterable, TextIO
import random

from .core import LogicError
from .card import get_deck
from .deal import Deal, NUM_PLAYERS, BIDDER_POS, DEALER_POS
from .player import Player
from .team import Team

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
    deals:  list[Deal]
    score:  list[int]   # indexed same as `teams`
    winner: Optional[Team]
    
    def __init__(self, teams: Iterable[Team]):
        """
        """
        self.teams = list(teams)
        if len(self.teams) != NUM_TEAMS:
            raise LogicError(f"Expected {NUM_TEAMS} teams, got {len(self.teams)}")
        self.deals  = []
        self.score  = [0] * NUM_TEAMS
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
        bidder_team = self.player_team(players[BIDDER_POS])
        dealer_team = self.player_team(players[DEALER_POS])
        self.score[bidder_team[0]] += deal.points[BIDDER_POS]
        self.score[dealer_team[0]] += deal.points[DEALER_POS]

    def set_winner(self) -> None:
        """
        """
        winner = None
        for i, team_score in enumerate(self.score):
            if team_score >= GAME_POINTS:
                winner = self.teams[i]
                break
        if not winner:
            raise LogicError("Winner not found")
        self.winner = winner

    def play(self) -> None:
        """
        """
        # TODO: randomize seating within teams!!!
        seats = [t.players[n] for n in range(TEAM_PLAYERS) for t in self.teams]
        """
        seats = []
        for player_num in range(TEAM_PLAYERS):
            for team in self.teams:
                seats.append(self.team.players[player_num])
        """
        assert len(seats) == NUM_PLAYERS
        dealer_idx = random.randrange(NUM_PLAYERS)  # relative to `seats`
        
        while max(self.score) < GAME_POINTS:
            bidder_idx = (dealer_idx + 1) % NUM_PLAYERS
            players = seats[bidder_idx:] + seats[:bidder_idx]
            deck = get_deck()
            deal = Deal(players, deck)
            self.deals.append(deal)

            deal.deal_cards()
            deal.do_bidding()
            if deal.is_passed():
                dealer_idx = (dealer_idx + 1) % NUM_PLAYERS
                continue
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
            print(f"\nDeal #{i + 1}:", file=file)
            deal.print(file)

        print("\nGame Score:", file=file)
        for j, team in enumerate(self.teams):
            print(f"  {team.name}: {self.score[j]}", file=file)

        if not self.winner:
            return

        print(f"Game Winner:\n  {self.winner}")
        
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
