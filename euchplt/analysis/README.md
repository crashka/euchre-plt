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

Extend `HandAnalysis` to determine a "hand strength" score given a trump suit
context, for use in bidding.  This score is used in the associated `StartegySmart`
class against thresholds based on bidding position to determine whether/what to bid.
We specify a number of config parameters to help compute this score.

Example parameter values (see base_config.yml for actual default values):

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

Overall score is based on subscores for the following aspects of the hand:

- Trump card strength
- Best off-suit strength
- Number of trump cards
- Number of off-aces
- Number of voids

Trump and off-suit strength subscores are computed by adding the values (based on
lookups in the `trump_values` and `suit_values` arrays) for all of the cards in each
suit, normalizing to the total available points for the suit, then multiplying by the
appropriate scoring coefficient.

For trump, the individual card values are (from above):

- 9 - 0 pts
- 10 - 0 pts
- J - n/a (promoted to R)
- Q - 1 pt
- K - 2 pts
- A - 4 pts
- L - 7 pts
- R - 10 pts

Thus, if the trump holding for the suit under consideration is L-K-10, the value
(based on lookup) is 7 + 2 + 0 = 9, which is then divided by total trump points (24)
and multiplied by the `trump_score` coefficient of 40 to get the subscore.  The same
method is applied for computing off-suit scores (9-through-A lookup, since there are
no bowers); the highest suit value is then divided by 16 and mutiplied by the
`max_suit_score` coefficient.

For the other scoring components, the lookup value is by number of trump cards in the
hand (thus, ascribing some value to 9s and 10s), number of off-aces, and number of
void suits, respectively.  That value is then multiplied by the corresponding
`scoring_coeff` number.  Note that the set of scoring coefficients don't have to add
up to 100, but keeping it so makes it easier to understand the relative weighting
between the scoring components.

All of the subscores added together yields the overall hand strengh score used by
`StrategySmart`.

## Full Docs

See [module-euchplt.analysis](https://crashka.github.io/euchre-plt/_build/html/euchplt.html#module-euchplt.analysis).
