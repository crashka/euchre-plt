#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from enum import Enum
from collections.abc import Iterable
from typing import TextIO
import random

from .core import DEBUG, LogicError
from .card import get_deck
from .deal import Deal, DealAttr, NUM_PLAYERS, BIDDER_POS, DEALER_POS
from .player import Player
from .team import Team

############
# GameStat #
############

class GameStat(Enum):
    DEALS_TOTAL       = "Total Deals"
    DEALS_PLAYED      = "Deals Played"
    DEALS_PASSED      = "Deals Passed"
    TRICKS            = "Tricks"
    POINTS            = "Points"
    # caller stats
    CALLS             = "Calls"
    CALLS_MADE        = "Calls Made"
    CALLS_ALL_5       = "Calls Made All 5"
    CALLS_EUCHRED     = "Calls Euchred"
    LONERS_CALLED     = "Loners Called"
    LONERS_MADE       = "Loners Made"
    LONERS_FAILED     = "Loners Failed"
    LONERS_EUCHRED    = "Loners Euchred"
    NL_CALLS          = "NL Calls"
    NL_CALLS_MADE     = "NL Calls Made"
    NL_CALLS_ALL_5    = "NL Calls Made All 5"
    NL_CALLS_EUCHRED  = "NL Calls Euchred"
    # defender stats
    DEFENSES          = "Defenses"
    DEF_LOSSES        = "Defense Losses"
    DEF_EUCHRES       = "Defense Euchres"
    DEF_LONERS        = "Defend Loners"
    DEF_LONER_LOSSES  = "Defend Loner Losses"
    DEF_LONER_STOPS   = "Defend Loner Stops"
    DEF_LONER_EUCHRES = "Defend Loner Euchres"
    DEF_ALONES        = "Defenses Alone"
    DEF_ALONE_LOSSES  = "Defend Alone Losses"
    DEF_ALONE_STOPS   = "Defend Alone Stops"
    DEF_ALONE_EUCHRES = "Defend Alone Euchres"

    def __str__(self):
        return self.value

NON_POS_STATS = {GameStat.DEALS_TOTAL,
                 GameStat.DEALS_PLAYED,
                 GameStat.DEALS_PASSED,
                 GameStat.TRICKS,
                 GameStat.POINTS}
# note, we don't really care if there is no order to POS_STATS since
# we won't (or shouldn't) ever want to iterate on this directly (at
# least not for reporting purposes)
POS_STATS = set(GameStat) - NON_POS_STATS

########
# Game #
########

NUM_TEAMS    = 2
TEAM_PLAYERS = 2
GAME_POINTS  = 10

class Game(object):
    """
    """
    # params/config
    teams:     list[Team]

    # state
    deals:     list[Deal]                  # sequential
    score:     list[int]                   # (points) indexed as `teams`
    stats:     list[dict[GameStat, int]]   # each stat indexed as `teams`
    pos_stats: list[dict[GameStat, list[int]]]  # tabulate stats by call_pos
    winner:    tuple[int, Team] | None     # tuple(idx, team)

    def __init__(self, teams: Iterable[Team], **kwargs):
        """
        """
        self.teams = list(teams)
        if len(self.teams) != NUM_TEAMS:
            raise LogicError(f"Expected {NUM_TEAMS} teams, got {len(self.teams)}")
        self.deals     = []
        self.score     = []
        self.stats     = [{stat: 0 for stat in GameStat} for _ in range(NUM_TEAMS)]
        self.pos_stats = [{stat: [0] * 8 for stat in POS_STATS} for _ in range(NUM_TEAMS)]
        self.winner    = None

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
        GS = GameStat

        if deal.is_passed():
            for pos in (BIDDER_POS, DEALER_POS):
                team_idx = self.player_team(players[pos])[0]
                team_stats = self.stats[team_idx]
                team_stats[GS.DEALS_TOTAL] += 1
                team_stats[GS.DEALS_PASSED] += 1
            return

        assert len(deal.points) == len(players)
        assert len(deal.tricks_won) == len(players)

        for pos in (BIDDER_POS, DEALER_POS):
            team_idx = self.player_team(players[pos])[0]
            self.score[team_idx] += deal.points[pos]

            team_stats = self.stats[team_idx]
            team_stats[GS.DEALS_TOTAL] += 1
            team_stats[GS.DEALS_PLAYED] += 1
            team_stats[GS.TRICKS] += deal.tricks_won[pos]
            team_stats[GS.POINTS] += deal.points[pos]

        call_team_idx = self.player_team(players[deal.caller_pos])[0]
        def_team_idx = self.player_team(players[deal.caller_pos ^ 0x01])[0]
        # this the position of the "call" (not caller), so range is 0-7!
        call_pos = deal.caller_pos + (0 if deal.discard else 4)

        def call_stat_incr(stat: GameStat, value: int = 1) -> None:
            self.stats[call_team_idx][stat] += value
            self.pos_stats[call_team_idx][stat][call_pos] += value

        def def_stat_incr(stat: GameStat, value: int = 1) -> None:
            self.stats[def_team_idx][stat] += value
            self.pos_stats[def_team_idx][stat][call_pos] += value

        # bidding/calling
        call_stat_incr(GS.CALLS)
        def_stat_incr(GS.DEFENSES)

        if DealAttr.GO_ALONE in deal.result:
            call_stat_incr(GS.LONERS_CALLED)
            def_stat_incr(GS.DEF_LONERS)
            if DealAttr.DEF_ALONE in deal.result:
                def_stat_incr(GS.DEF_ALONES)
        else:
            call_stat_incr(GS.NL_CALLS)

        # playing/results
        if DealAttr.MAKE in deal.result:          # MADE...
            assert DealAttr.EUCHRE not in deal.result
            call_stat_incr(GS.CALLS_MADE)
            def_stat_incr(GS.DEF_LOSSES)

            if DealAttr.GO_ALONE in deal.result:  # loner made
                if DealAttr.ALL_5 in deal.result:
                    call_stat_incr(GS.CALLS_ALL_5)
                    call_stat_incr(GS.LONERS_MADE)
                    def_stat_incr(GS.DEF_LONER_LOSSES)
                    if DealAttr.DEF_ALONE in deal.result:
                        def_stat_incr(GS.DEF_ALONE_LOSSES)
                else:
                    call_stat_incr(GS.LONERS_FAILED)
                    def_stat_incr(GS.DEF_LONER_STOPS)
                    if DealAttr.DEF_ALONE in deal.result:
                        def_stat_incr(GS.DEF_ALONE_STOPS)
            else:                                 # non-loner made
                call_stat_incr(GS.NL_CALLS_MADE)
                if DealAttr.ALL_5 in deal.result:
                    call_stat_incr(GS.CALLS_ALL_5)
                    call_stat_incr(GS.NL_CALLS_ALL_5)
        else:                                     # NOT MADE...
            assert DealAttr.EUCHRE in deal.result
            call_stat_incr(GS.CALLS_EUCHRED)
            def_stat_incr(GS.DEF_EUCHRES)

            if DealAttr.GO_ALONE in deal.result:  # loner euchred
                call_stat_incr(GS.LONERS_EUCHRED)
                def_stat_incr(GS.DEF_LONER_EUCHRES)
                if DealAttr.DEF_ALONE in deal.result:
                    def_stat_incr(GS.DEF_ALONE_EUCHRES)
            else:                                 # non-loner euchred
                call_stat_incr(GS.NL_CALLS_EUCHRED)

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
        # Note, we keep the players in order here (tm0-pl0, tm1-pl0, etc.), it
        # is up to the caller to specify who actually sits where
        seats = [t.players[n] for n in range(TEAM_PLAYERS) for t in self.teams]
        assert len(seats) == NUM_PLAYERS
        # "flip for deal" (indexed relative to `seats`)
        dealer_idx = random.randrange(NUM_PLAYERS)

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

    def print(self, file: TextIO = sys.stdout, verbose: int = 0) -> None:
        """Setting the `verbose` flag (or DEBUG mode) will print out details
        for individual deals, as well as printing game stats
        """
        verbose = max(verbose, DEBUG)

        print("Teams:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team}", file=file)
            for j, player in enumerate(team.players):
                print(f"    {player}", file=file)

        if verbose:
            for i, deal in enumerate(self.deals):
                print(f"Deal #{i + 1}:", file=file)
                if verbose > 1:
                    deal.print(file=file)
                else:
                    deal.print_score(file=file)

        self.print_score(file=file)
        if verbose:
            self.print_stats(file=file)

    def print_score(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Game Score:", file=file)
        for i, team in enumerate(self.teams):
            print(f"  {team.name}: {self.score[i]}", file=file)

        if not self.winner:
            return

        print(f"Game Winner:\n  {self.winner[1]}")

    def print_stats(self, file: TextIO = sys.stdout) -> None:
        """
        """
        print("Game Stats:", file=file)
        for i, team in enumerate(self.teams):
            mystats = self.stats[i]
            print(f"  {team.name}:", file=file)
            for stat in GameStat:
                print(f"    {stat.value + ':':24} {mystats[stat]:8}", file=file)

########
# main #
########

def main() -> int:
    """Built-in driver to run through a simple/sample game
    """
    players     = [Player("Player 02"),
                   Player("Player 03"),
                   Player("Player 06"),
                   Player("Player 07")]
    teams       = [Team([players[0], players[1]]),
                   Team([players[2], players[3]])]

    game = Game(teams)
    game.play()
    game.print(verbose=1)

    return 0

if __name__ == '__main__':
    sys.exit(main())
