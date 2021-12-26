#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from collections.abc import Iterable
from typing import Optional, TextIO
import shelve

from .core import DEBUG, DataFile, ArchiveDataFile
from .team import Team
from .match import Match

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
    elo_db:        str
    reset_ratings: bool
    use_margin:    bool
    init_rating:   float
    d_value:       int
    k_factor:      int
    team_ratings:  dict[str, float]        # indexed by team name
    ratings_hist:  dict[str, list[float]]  # list of updates, indexed by team name

    def __init__(self, teams: Iterable[Team], params: dict = None):
        params = params or {}
        self.elo_db        = params.get('elo_db')        or DFLT_ELO_DB
        self.reset_ratings = params.get('reset_ratings') or False
        self.use_margin    = params.get('use_margin')    or False
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

    def get_sorted(self) -> tuple[str, float]:
        by_rating = sorted(self.team_ratings.items(), key=lambda s: s[1], reverse=True)
        for item in by_rating:
            yield item

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
                if self.use_margin:
                    s.append(match.score[i] / sum(match.score))
                else:
                    s.append(int(match.winner[0] == i))
                r_delta = self.k_factor * (s[i] - e[i])
                self.team_ratings[team.name] += r_delta
                self.ratings_hist[team.name].append(self.team_ratings[team.name])

    def _update_collective(self, matches: Iterable[Match]) -> None:
        """We sum the inbound ratings and scores, and do single bulk computations
        for some segment of the tournament in which inbound ratings are fixed.

        Note that this implementaion degenerates into the sequential case above
        if individual teams don't play multiple times in `matches`, so we can
        actually just always use this if sequential bahavior isn't explicitly
        needed (for less repeated code, at a very slight performance penalty)
        """
        active_teams = set()  # by team name
        e = {name: 0.0 for name in self.team_ratings}  # sum of expected scores
        s = {name: 0.0 for name in self.team_ratings}  # sum of actual scores
        for match in matches:
            r = []  # inbound rating
            q = []
            for i, team in enumerate(match.teams):
                active_teams.add(team.name)
                r.append(self.team_ratings[team.name])
                q.append(pow(10.0, r[i] / self.d_value))
            # loop again, since we need complete `q`
            for i, team in enumerate(match.teams):
                e[team.name] += q[i] / sum(q)
                if self.use_margin:
                    s[team.name] += match.score[i] / sum(match.score)
                else:
                    s[team.name] += int(match.winner[0] == i)

        for name in self.team_ratings:
            if name in active_teams:
                r_delta = self.k_factor * (s[name] - e[name])
                self.team_ratings[name] += r_delta
                self.ratings_hist[name].append(self.team_ratings[name])
            else:
                self.ratings_hist[name].append(None)

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
        for name, cur_rating in self.get_sorted():
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

    def iter_elo(self) -> dict[str, float]:
        """Ratings history data corresponding to the fields returned by `elo_header()`
        """
        TEAM_COL = 'Team'
        for name, ratings in self.ratings_hist.items():
            team_hist = {f"Elo {i}": val for i, val in enumerate(ratings)}
            hist_row = {TEAM_COL: name} | team_hist
            yield hist_row
