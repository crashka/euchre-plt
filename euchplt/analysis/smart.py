# -*- coding: utf-8 -*-

from ..core import ConfigError, cfg, log
from ..card import SUITS, Suit, Rank, Card
from ..euchre import Hand
from .base import SUIT_CTX, HandAnalysis

#####################
# HandAnalysisSmart #
#####################

class HandAnalysisSmart(HandAnalysis):
    """Extend ``HandAnalysis`` to determine a "hand strength" score given a trump suit
    context, for use in bidding.  This score is used in the associated ``StartegySmart``
    class against thresholds based on bidding position to determine whether/what to bid.
    We specify a number of config parameters to help compute this score.

    Example parameter values (see base_config.yml for actual default values)::

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

    Overall score is based on subscores for the following aspects of the hand:

    - Trump card strength
    - Best off-suit strength
    - Number of trump cards
    - Number of off-aces
    - Number of voids

    Trump and off-suit strength subscores are computed by adding the values (based on
    lookups in the ``trump_values`` and ``suit_values`` arrays) for all of the cards in
    each suit, normalizing to the total available points for the suit, then multiplying by
    the appropriate scoring coefficient.

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
    and multiplied by the ``trump_score`` coefficient of 40 to get the subscore.  The same
    method is applied for computing off-suit scores (9-through-A lookup, since there are
    no bowers); the highest suit value is then divided by 16 and mutiplied by the
    ``max_suit_score`` coefficient.

    For the other scoring components, the lookup value is by number of trump cards in the
    hand (thus, ascribing some value to 9s and 10s), number of off-aces, and number of
    void suits, respectively.  That value is then multiplied by the corresponding
    ``scoring_coeff`` number.  Note that the set of scoring coefficients don't have to add
    up to 100, but keeping it so makes it easier to understand the relative weighting
    between the scoring components.

    All of the subscores added together yields the overall hand strengh score used by
    ``StrategySmart``.
    """
    # the following annotations represent the parameters that are specified in the config
    # file for the class name under `base_analysis_params` (and which may be overridden
    # under a `hand_analysis` parameter for a parent strategy's configuration)
    trump_values:     list[int]
    suit_values:      list[int]
    num_trump_scores: list[float]
    off_aces_scores:  list[float]
    voids_scores:     list[float]
    scoring_coeff:    dict[str, int]

    def __init__(self, hand: Hand, **kwargs):
        """Note that config parameters passed in through ``kwargs`` will override the
        values specified in base_config.yml.  The entire ``scoring_coeff`` dict must be
        provided if overriding any of the individual coefficients.
        """
        super().__init__(hand)
        class_name = type(self).__name__
        base_params = cfg.config('base_analysis_params')
        if class_name not in base_params:
            raise ConfigError(f"Analysis class '{class_name}' does not exist")
        for key, base_value in base_params[class_name].items():
            setattr(self, key, kwargs.get(key) or base_value)
        pass  # TEMP: for debugging!!!

    def suit_strength(self, suit: Suit, trump_suit: Suit) -> float:
        """Returns the suit strength (sum of card values, normalized to total points for
        the suit) given a trump context.  Note that this call requires that jacks be
        replaced by BOWER cards (rank of ``right`` or ``left``).
        """
        value_arr = self.trump_values if suit == trump_suit else self.suit_values
        tot_value = 0
        suit_cards = self.get_suit_cards(trump_suit)[suit]
        for card in suit_cards:
            tot_value += value_arr[card.rank.idx]
        return tot_value / sum(value_arr)

    def hand_strength(self, trump_suit: Suit) -> float:
        """Return the overall hand strength score given a trump suit context, based on
        parameters and multiplier coefficients specified for the instance (base config
        plus constructor overrides).
        """
        # KINDA HACKY: local variables need to align with keys in `self.scoring_coeff`
        # (enforced by the assert in the loop, below)
        trump_score = None
        suit_scores = []  # no need to track associated suits, for now

        for suit in SUITS:
            if suit == trump_suit:
                trump_score = self.suit_strength(suit, trump_suit)
            else:
                suit_scores.append(self.suit_strength(suit, trump_suit))

        max_suit_score  = max(suit_scores)
        num_trump       = len(self.trump_cards(trump_suit))
        num_trump_score = self.num_trump_scores[num_trump]
        off_aces        = len(self.off_aces(trump_suit))
        off_aces_score  = self.off_aces_scores[off_aces]
        voids           = len(set(self.voids(trump_suit)) - {trump_suit})
        # useful voids capped by number of trump
        voids           = max(min(voids, num_trump - 1), 0)
        voids_score     = self.voids_scores[voids]

        strength = 0.0
        log.debug(f"hand: {self.hand} (trump: {trump_suit})")
        for score, coeff in self.scoring_coeff.items():
            raw_value = locals()[score]
            assert isinstance(raw_value, float)
            score_value = locals()[score] * coeff
            log.debug(f"  {score:15}: {score_value:6.2f} ({raw_value:.2f} * {coeff:d})")
            strength += score_value
        log.debug(f"{'hand_strength':15}: {strength:6.2f}")
        return strength

    def turn_card_rank(self, turn_card: Card) -> Rank:
        """SUPER-HACKY: this doesn't really belong here, need to figure out a nicer way of
        doing this (needed by ``StrategySmart.bid()``)!!!
        """
        ctx = SUIT_CTX[turn_card.suit]
        return turn_card.effcard(ctx).rank
