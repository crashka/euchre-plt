# Strategy

This module provides classes that implement bidding and playing strategies for players
and teams.  Note that `Strategy` (abstract base class) can also be subclassed by other
modules for special purpose use (e.g. "traversal" strategies in the `ml` module).

## Classes

### Strategy

Abstract base class, cannot be instantiated directly.  Subclasses should be instantiated
using `Strategy.new(<strat_name>)`.

Subclasses must implement the following methods:

- `bid()`
- `discard()`
- `play_card()`
- `notify()` – *\[optional]* handle notifications (e.g. `DEAL_COMPLETE`)

The context for all calls is provided by `DealState`, which is defined as follows (in
euchre.py):

```python
class DealState(NamedTuple):
    pos:              int
    hand:             Hand
    turn_card:        Optional[Card]
    bids:             list[Bid]
    tricks:           list[Trick]
    contract:         Optional[Bid]
    caller_pos:       Optional[int]
    go_alone:         Optional[bool]
    def_alone:        Optional[bool]
    def_pos:          Optional[int]
    played_by_suit:   dict[Suit, Hand]
    unplayed_by_suit: dict[Suit, set[Card]]
    tricks_won:       list[int]
    points:           list[int]
    player_state:     dict
```

### StrategyRandom

Randomly pick between valid bids, discards, and card plays.  Note that there are a
number of magic numbers hardwired into the implementation (e.g. thresholds for whether
or when to bid, go/defend alone, etc.), which we may want to parameterize for some
visibility (this is, after all, a teaching tool).

### StrategySimple

Represents minimum logic for passable play--very basic strategy, fairly
conservative (though we add several options for more aggressive play).

`aggressive` parameter (int) bit fields (can be OR'ed together):

- `0x01` - partner is winning, but play high (pre-emptive) from the third seat rather than
  duck
- `0x02` - take high (if possible) from second or third seat, rather than lower take
  (e.g. use A instead of Q on a lead of 9)

TODO (maybe): parameterize some of the magic numbers in this code!?!?

### StrategySmart

Strategy based on rule-based scoring/strength assessments, both for bidding and
playing.  The rules are parameterized, so variations can be specified in the config
file.

Example parameter values for bidding::

```yaml
  hand_analysis:    # keep this empty here, but may be overridden by
                    # individual strategies
  turn_card_value:  [10, 15, 0, 20, 25, 30, 0, 50]
  turn_card_coeff:  [25, 25, 25, 25]
  bid_thresh:       [35, 35, 35, 35, 35, 35, 35, 35]
  alone_margin:     [10, 10, 10, 10, 10, 10, 10, 10]
  def_alone_thresh: [35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35]
```

Brief description of bid parameters:

- `hand_analysis` - override base config parameters for `HandAnalysisSmart`
- `turn_card_value` - value for turn card, indexed by rank (9-R, e.g. A = 30, above)
- `turn_card_coeff` - multiplier for `turn_card_value`, indexed by seat position
  (product to be added to hand strength)
- `bid_thresh` - total strength needed to bid, indexed by bid position (across 2
  rounds)
- `alone_margin` - margin above `bid_thresh` needed to go alone, indexed by bid
  positions
- `def_alone_thresh` - total strength needed to defend alone, indexed by bid
  position

FUTURE: there is an opportunity to build a framework for optimizing the various
parameters, either in an absolute sense, or possibly relative to different opponent
profiles.

### StrategyML

Invocation of ML-based strategies, created by the framework defined in [ml/](../../ml).

### StrategyRemote

Invocation of remote strategies through the
[EuchreEndpoint](https://github.com/crashka/EuchreEndpoint) interface.

## Full Docs

See [module-euchplt.strategy](https://crashka.github.io/euchre-plt/_build/html/euchplt.html#module-euchplt.strategy).
