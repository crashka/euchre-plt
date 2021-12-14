# -*- coding: utf-8 -*-

from typing import Union, Iterable

from .core import cfg, ConfigError
from .player import Player
from .strategy import Strategy

########
# Team #
########

MIXED_STRATEGY = "mixed strategy"
DFLT_PLAYER_IDS = ("Player A", "Player B")

class Team:
    name:          str
    # note that the following is the name of configured strategy in the config
    # file, and not the instantiated `Strategy` object itself (as in `Player`)
    team_strategy: str
    players:       list[Player]

    def __init__(self, team_def: Union[str, Iterable[Player]]):
        """A team can be defined by an entry in the config file; or by an iterable (with
        two entries) of instantiated `Player` objects, in which case a team name will be
        generated from the player names
        """
        if isinstance(team_def, str):
            teams = cfg.config('teams')
            if team_def not in teams:
                raise RuntimeError(f"Team '{team_def}' is not known")
            strategy = teams[team_def].get('strategy')
            if not strategy:
                raise ConfigError(f"'strategy' not specified for team '{team_def}'")
            self.name = team_def
            self.team_strategy = strategy
            player_names = [f"{self.name} - {p}" for p in DFLT_PLAYER_IDS]
            self.players = [Player(player_names[0], Strategy.new(self.team_strategy)),
                            Player(player_names[1], Strategy.new(self.team_strategy))]
        else:
            self.players = list(team_def)
            if len(self.players) != 2:
                raise RuntimeError(f"Expected 2 players, got {len(self.players)}")
            self.name = '/'.join(str(p) for p in self.players)
            if type(self.players[0].strategy) is type(self.players[1].strategy):
                self.team_strategy = type(self.players[0].strategy).__name__
            else:
                self.team_strategy = MIXED_STRATEGY

    def __str__(self):
        return f"{self.name} ({self.team_strategy})"
