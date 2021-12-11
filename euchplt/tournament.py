#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional, TypeVar, Iterable, Iterator

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

##############
# Tournament #
##############

class Tournament:
    """
    """
    pass

########
# main #
########

import sys

def main() -> int:
    """Built-in driver to invoke various utility functions for the module
    """
    tourney_teams_even = ["Team 1",
                          "Team 2",
                          "Team 3",
                          "Team 4",
                          "Team 5",
                          "Team 6",
                          "Team 7",
                          "Team 8"]

    tourney_teams_odd =  ["Team 1",
                          "Team 2",
                          "Team 3",
                          "Team 4",
                          "Team 5",
                          "Team 6",
                          "Team 7",
                          "Team 8",
                          "Team 9"]

    BYE = "-bye-"

    def p(t: TO) -> str:
        return str(t or BYE)

    print("Tournament - Even Entries")
    for i, matchups in enumerate(round_robin_matchups(tourney_teams_even)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):10s} vs. {p(matchup[1]):10s}")

    print("\nTournament - Odd Entries")
    for i, matchups in enumerate(round_robin_matchups(tourney_teams_odd)):
        print(f"  Round {i+1} matchups:")
        for matchup in matchups:
            print(f"    {p(matchup[0]):10s} vs. {p(matchup[1]):10s}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
