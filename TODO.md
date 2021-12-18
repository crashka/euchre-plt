### TODO Items ###

_[In roughly in priority order, within each section...]_

#### Smaller Stuff ####
- Memory management for long-running tounaments; i.e. process/document, and
  then release, completed matches, base on an interval, with appropriate
  notifications to subclass implementaions
- Move Elo stuff to its own module; allow strategy subclasses to control
  Elo computation
- Print incremental results, stats (e.g. round robin pass)
- Report rank information for stats
- Dump config parameters for tournament runs
- Modified round robin format, where lower teams drop out in stages
- Performance tuning for 'effevel', 'effcard', and 'trump_suit'
- Push 'pos_stats' settings down to match and game
- Refactor polymorphic modules into subpackages (specifically, 'strategy'
  and 'hand_analysis')
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
