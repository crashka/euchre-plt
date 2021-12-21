### TODO Items ###

_[In roughly in priority order, within each section...]_

#### Smaller Stuff ####
- Performance tuning for `cards_by_suit`, `effsuit`, `efflevel`
- Dump config parameters for tournament runs
- Push `pos_stats` settings down to match and game
- Refactor polymorphic modules into subpackages (specifically, `strategy`
  and `hand_analysis`)

#### Bigger/Feature-Level Stuff ####
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
- ML learning frameworks
    - Bidding models
    - Playing models
- Add notifications to Deal-Player interface (to support external 'Player'
  developerment)
    - Contract/Pass
    - Trick
- Dynamic strategy based on match/game or deal situation/scenario
- Add support for Java player implementation (jpype or py4j)
