### TODO Items ###

_[In roughly in priority order, within each section...]_

#### Smaller Stuff ####
- Rename 'euchplt' to 'pltform'
- Add play parameters for 'StrategySmart' ("Delta" family)
- Track stats/outcome by bid/call position
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
- Add notifications to Deal-Player interface (to support external 'Player' developerment)
    - Contract/Pass
    - Trick
- Add support for Java player implementation (jpype or py4j)
