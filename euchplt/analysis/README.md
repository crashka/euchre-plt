# Analysis

This module provides helper classes for the `strategy` module.  The primary base
classes are `Hand Analysis` and `PlayAnalysis`, both of which can be subclassed by any
strategy that requires additional or specialized functionality.

## Classes

### HandAnalysis

This class provides helper methods for evaluating hands, typically by extracting
useful subsets (i.e. lists) of cards, given a trump suit context.  Counts can then be
easily derived using `len()`.  This class is generally only used directly in the
bidding process, during which the underlying hand does not change (there is no caching
of results).

Note that these calls still work if/as the hand changes (e.g. cards are swapped and/or
played), thus `PlayAnalysis` contains wrapper methods which automatically pass in the
trump suit context (since it will already be known for the deal).

### PlayAnalysis

This class provides helper methods for evaluating hands during the play process.
It contains wrappers for useful `HandAnalysis` methods (which will reflect the current
state of the hand in the deal), as well as additional functions helpful during play.

### HandAnalysisSmart

Extends `HandAnalysis` to determine a "hand strength" score given a trump suit
context, for use in bidding.  This score is used in the associated `StartegySmart`
class against various thresholds (based on bidding position) to determine whether/what
to bid.

The overall score is based on subscores for the following aspects of the hand:

- Trump card strength
- Best off-suit strength
- Number of trump cards
- Number of off-aces
- Number of voids

These are the config parameters used to help compute this score (example values shown
here--see base_config.yml for the actual base values)::

```yaml
  trump_values:     [0, 0, null, 1, 2, 4, 7, 10]
  suit_values:      [0, 0, 0, 1, 5, 10]
  num_trump_scores: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
  off_aces_scores:  [0.0, 0.2, 0.5, 1.0]
  voids_scores:     [0.0, 0.3, 0.7, 1.0]
  scoring_coeff:
    trump_score:      40
    max_suit_score:   10
    num_trump_score:  20
    off_aces_score:   15
    voids_score:      15
```

Here are descriptions of the parameters:

- `trump_values` - value for each trump card in the hand, indexed by card rank (9-R,
  which includes L and ignores the J position [promoted to R]), to be added together
  and normalized for total trump subscore
- `suit_values` - value for each card in non-trump suits, indexed by card rank (9-A,
  noting that J does not exist for next suit), to be added together and normalized for
  each suit to get total suit subscore
- `num_trump_scores` - subscore for number of trump cards in the hand, indexed by
  count (0-5)
- `off_aces_scores` - subscore for number of off-aces in the hand, indexed by count
  (0-3)
- `voids_scores` - subscore for number of void suits in the hand, indexed by count
  (0-3)
- `scoring_coeff` - array of coefficients to be multipled by the corresponding
  subscores (as described above) for their contribution to the overall hand strength
  score

Normalization for trump and off-suit subscores means dividing the aggregate card value
by the total number of points available for the category.  Thus, if the trump holding
for the suit under consideration is L-K-10, the sum (based on lookup) is 7 + 2 + 0 =
9, which is then divided by the total available points (24 in this case), before being
multiplied by the `trump_score` coefficient.  For off-suits, only the highest
normalized suit value is mulitplied by the `max_suit_score` coefficient.

The weighted subscores are added together to yield the overall hand strengh score used
by `StrategySmart`.  Note that the set of scoring coefficients don't have to add up
to 100, but specifying it thus makes it easier to understand the relative weighting
between the scoring components.

## Full Docs

See [module-euchplt.analysis](https://crashka.github.io/euchre-plt/_build/html/euchplt.html#module-euchplt.analysis).
