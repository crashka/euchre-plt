# euchre-plt – Euchre Platform

## Overview

This project is composed of two main components:

- An extensible model upon which to develop **euchre-playing strategies**, whether
  heuristic- or ML-based
- A program for running games, matches, or full-blown **tournaments between strategies**

Both of these components are presented as frameworks that are extensible in code, and
further modifiable/tweakable through configuration.  The base classes for the two
components are defined in the `strategy` and `tournament` modules, respectively (both
under `euchplt`).  Illustrative subclass implementations and associated configuration
parameters are provided as pre-built examples that can be used as either prototypes or
starting points for additional development.

Also included in this project are two secondary components that support the primary
purposes above:

- A module for generating euchre **bidding and deal-playing data** that can be used for
  **training models** that underlie ML-based strategies
- An HTTP-based bridge through which **remote programs** can be invoked to compete against
  local strategies; the remote interface is specified in the
  [EuchreEndpoint](https://github.com/crashka/EuchreEndpoint) project

## Setup

Run the following to install the required libraries (only needed once after cloning the
repo):

``` bash
$ pip install -r requirements.txt
$ pip install -e .
```

Note that this project was developed under Python 3.11, so that would be the minimum
recommended version.

## Walkthrough

We'll take a walkthrough of the main components by way of an example.

### Running a Tournament

Here is the command to run a sample tourament:

``` bash
$ tournament run_tournament "demo" stats_file=demo_stats.tsv elo_file=demo_elo.tsv
```

And here is the tail end of the output for this run (slightly reformatted for readability;
the unedited full output is provided in
[examples/demo_output.txt](examples/demo_output.txt)):

```
Pass 19 Leaderboard:
                                                 Elo        Elo        Win %      Elo Rat
  Team          Wins       Losses     Win %      Points     Rating     Rank       Rank
  ----          ----       ------     -----      ------     ------     -----      -------
  Team 16       89         51         63.6       79.1       1542.7     1          1
  Team 10       86         54         61.4       76.4       1532.7     2          3
  Team 06       82         58         58.6       78.7       1540.3     3          2
  Team 12       82         58         58.6       73.2       1512.2     3          4
  Team 14       76         64         54.3       73.0       1510.1     5          5
  Team 08       63         77         45.0       69.4       1498.1     6          6
  Team 02       47         93         33.6       57.9       1444.1     7          7
  Team 04       35         105        25.0       52.3       1419.7     8          8

Tournament Score:
  Team 16: 89 (79.10)
  Team 10: 86 (76.36)
  Team 06: 82 (78.67)
  Team 12: 82 (73.18)
  Team 14: 76 (73.03)
  Team 08: 63 (69.37)
  Team 02: 47 (57.93)
  Team 04: 35 (52.35)

Tournament Winner:
  Team 16

Elo Ratings:
  Team 16: 1542.7
  Team 06: 1540.3
  Team 10: 1532.7
  Team 12: 1512.2
  Team 14: 1510.1
  Team 08: 1498.1
  Team 02: 1444.1
  Team 04: 1419.7
```

This shows that Team 16 was the tournament winner, with a record of 89-51.  Team 16 also
had the highest Elo rating, at 1542.7.  Note that Elo rating doesn't always correspond to
the tournament results (depending on tournament format, as well as luck of the cards—see
results for Team 06 and Team 10 in this run), but it is generally a close indicator of
final positions in touraments involving a sufficient amount of game play.

Here is an explanation of the command line arguments for the sample run above:

- `"demo"` – the name of the tournament to run; it is defined in the
  [config/tournaments.yml](config/tournaments.yml) config file (see below)
- `stats_file` – whether to generate a file containing detailed tournament statistics for
  each team; the specified file is created in the [data/](data) subdirectory for the
  project
- `elo_file` – whether to generate a file containing the Elo rating round-by-round for
  each team; this file (if specified) is also created in the [data/](data) subdirectory

For reference, here is the full help string for the `tournament` command:

```
Built-in driver to invoke various utility functions for the module

Usage: tournament.py <func_name> [<args> …]

Functions/usage:

- round_robin_bracket [teams=<num_teams>]
- run_tournament <name> [match_games=<int>] [passes=<int>] [stats_file=<stats_file>]
      [reset_elo=<bool>] [elo_update=<tourn_unit>] [elo_file=<elo_file>] [rand_seed=<int>]
      [verbose=<level>] [seeding=<seed_tourn_name>]
```

Command line arguments often override the values defined in the config file (which, in
turn, often override default values hardwired into the code, e.g. `DFLT_MATCH_GAMES = 2`).

### Tournament Definitions

Here is the definition for the `"demo"` tournament in the
[config/tournaments.yml](config/tournaments.yml) config file:

``` yaml
    demo:
      tourn_class:     RoundRobin
      tourn_params:
        match_games:     5
        passes:          20
        reset_elo:       true
        elo_params:
          elo_db:          elo_rating_600.db
          use_margin:      true
          d_value:         600
          k_factor:        8
      teams:
        - Team 02
        - Team 04
        - Team 06
        - Team 08
        - Team 10
        - Team 12
        - Team 14
        - Team 16
```

Let's examine each of the configuration parameters here:

- `tourn_class` – the subclass in the `tournament` module that implements the tournament
  format
  - In addition to `RoundRobin`, other tournament classes include: `HeadToHead`,
    `ChallengeLadder`, `SingleElimination`, and `DoubleElimination`
- `match_games` – the number of games needed win a match (individual match-up within a
  round)
  - A value of `5` here indicates a best five of nine game format (as indicated above,
    default is best two of three games)
- `passes` – the number of full round-robin cycles (where each team plays every other team
  one time) for the tournament
- `reset_elo` – whether to reset Elo ratings (back to 1500) for all teams before running
  the tournament
  - Reasons for *not* resetting include: (1) maintaining Elo ratings for teams across
    tournaments; or (2) preserving the Elo ratings for a preliminary tournament/round to
    use as seeding positions for a main tournament
- `elo_params`
  - `elo_db` – name of the file (within the [data/](data) directory) for maintaining Elo
    rating information
  - `use_margin` – whether to use victory margins (i.e. game scores within a match) in
    computing Elo ratings (`false` indicates that only match-level wins are counted)
  - `d_value` - the "scaling factor" for the [Elo rating
    formula](https://en.wikipedia.org/wiki/Elo_rating_system#Mathematical_details)
    (default value is 400)
  - `k_factor` – the k-factor for the Elo rating formula (default value is 24)

Note that these parameter settings (including the `elo_params` subparameters) override the
values set for the tournament subclass in the `base_tourn_params` section of the
[config/base_config.yml](config/base_config.yml) "base" config file (as well as the
hardwired defaults in code).

### Teams and Strategies

Now let's take a look at how the teams and their strategies are defined.  Each of the
teams participating in a tournament must be defined in the
[config/players_teams.yml](config/players_teams.yml) config file.  Note that individual
players can also be defined in the same config file, so that customer teams with mixed
strategies can be configured.  For most tournaments, however, it is assumed that both
players on a team will utilize the same strategy (in order for the strategies themselves
to be pitted against each other), so we will only focus on team definitions for now.

Currently, the only parameter for each team is `strategy`; there is no other persistent or
indidvidual identification.  Here are the definitions for the teams in the sample
tournament above (with each team implementing a different strategy):

``` yaml
  teams:
    Team 02:
      strategy:        Bravo 1
    Team 04:
      strategy:        Bravo 2
    Team 06:
      strategy:        Charlie 1
    Team 08:
      strategy:        Charlie 2
    Team 10:
      strategy:        Charlie 3
    Team 12:
      strategy:        Charlie 4
    Team 14:
      strategy:        Charlie 5
    Team 16:
      strategy:        Charlie 6
```

Here are the first few strategy definitions in the
[config/strategies.yml](config/strategies.yml) config file for the teams in our sample
tourament:

``` yaml
    Bravo 1:
      comments:         "base StrategySimple configuration"
      module_path:      euchplt.strategy
      base_class:       StrategySimple
    Bravo 2:
      comments:         "aggressive play for StrategySimple"
      module_path:      euchplt.strategy
      base_class:       StrategySimple
      strategy_params:
        aggressive:       0x01
    Charlie 1:
      comments:         "base StrategySmart configuration"
      module_path:      euchplt.strategy
      base_class:       StrategySmart
    Charlie 2:
      comments:         "raise all bid thresholds"
      module_path:      euchplt.strategy
      base_class:       StrategySmart
      strategy_params:
        hand_analysis:
          # overrides for HandAnalysisSmart base params
        bid_thresh:       [38, 38, 38, 38, 38, 38, 38, 38]
```

Here is a rundown of the various parameters:

- `comments` – informational description of the strategy
- `module_path` – all strategy modules should be under `euchplt.strategy`
- `base_class` – name of the subclass that implements the strategy
- `strategy_params` – the subparameters in this section are specific to the strategy
  subclass (i.e. tied to the code); details on the inner workings and dedicated
  configuration subparameters will be provided in the README for the
  [euchplt/strategy](euchplt/strategy) directory

Similar to the tournament parameters described above, strategy paramers in this file
override base values specified in the `base_strategy_params` section of
[config/base_config.yml](config/base_config.yml) config file.

Note that the `Bravo 1` and `Charlie 1` strategies specify the default configuration for
the `StrategySimple` and `StrategySmart` subclasses, respectively.  All of the other
strategies used by teams in the sample tournament specify overrides for one or more of the
strategy-specific subparameters.

## Additional Documentation

More detailed descriptions of the individual modules will be found in the README for the
various subdirectories (work in process).

For full module-/class-level documentation, see
[https://crashka.github.io/euchre-plt](https://crashka.github.io/euchre-plt) (generated by
Sphinx from [docs/](docs)).

## Current Work in Process

**To Do**

- Implement `StrategyRemote`, which will invoke the
  [EuchreEndpoint](https://github.com/crashka/EuchreEndpoint) interface for Java-based
  strategies
- Detailed module-level documentation (README's) for both `euchplt` and `ml`

## License

This project is licensed under the terms of the MIT License.
