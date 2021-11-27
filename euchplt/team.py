# -*- coding: utf-8 -*-

from typing import Iterable

from .player import Player

########
# Team #
########

class Team:
    """
    """
    name:    str
    players: list[Player]
    
    def __init__(self, players: Iterable[Player]):
        self.players = list(players)
        if len(self.players) != 2:
            raise RuntimeError(f"Expected 2 players, got {len(self.players)}")

        self.name = ' / '.join(str(p) for p in self.players)

    def __str__(self):
        return self.name
