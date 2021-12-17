### TODO Items ###

_[In roughly in priority order, within each section...]_

#### Smaller Stuff ####
- Rename 'euchplt' to 'pltform' *[do we still want to do this???]*
- Add match- and game-level parameters, e.g. 'match_games'
- Move Elo stuff to its own module; allow strategy subclasses to control
  Elo computation
- Push 'pos_stats' settings down to match and game
- Report rank information for stats
- Dump config parameters for tournament runs
- Refactor polymorphic modules into subpackages (specifically, 'strategy'
  and 'hand_analysis')
- Memory management for long-running tounaments; i.e. process/document, and
  then release, completed matches, base on an interval, with appropriate
  notifications to subclass implementaions
- Strategy tracker, for manual analysis of problem stats
    - Bidding optimization
        - NL Euchre Pct (too aggressive?)
        - Loner Euchre Pct (too aggressive?)
        - NL All 5 Pct (missed loner opportunity?)
        - Defend Alone Lose-to-Euchre Pct (too aggressive?)
    - Playing optimization
        - Call Make Pct
        - NL Call Pct
- Optimize base params for 'HandAnalysisSmart' and 'StrategySmart'
- Print incremental stats (e.g. round robin pass)

#### Bigger/Feature-Level Stuff ####
- ML learning frameworks
    - Bidding models
    - Playing models
- Add notifications to Deal-Player interface (to support external 'Player'
  developerment)
    - Contract/Pass
    - Trick
- Dynamic strategy based on match/game or deal situation/scenario
- Add support for Java player implementation (jpype or py4j)
