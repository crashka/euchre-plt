# -*- coding: utf-8 -*-

from ..core import ConfigError, cfg, log
from ..card import SUITS, Suit, Rank, Card
from ..euchre import Hand
from .base import HandAnalysis

#####################
# HandAnalysisSmart #
#####################

StrengthTuple = tuple[float, float, int]  # strength, raw_value, coeff

class HandAnalysisSmart(HandAnalysis):
    """Extends ``HandAnalysis`` to determine a "hand strength" score given a trump suit
    context, for use in bidding.  This score is used in the associated ``StartegySmart``
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

    Here are descriptions of the parameters:

    - ``trump_values`` - value for each trump card in the hand, indexed by card rank (9-R,
      which includes L and ignores the J position [promoted to R]), to be added together
      and normalized for total trump subscore
    - ``suit_values`` - value for each card in non-trump suits, indexed by card rank (9-A,
      noting that J does not exist for next suit), to be added together and normalized for
      each suit to get total suit subscore
    - ``num_trump_scores`` - subscore for number of trump cards in the hand, indexed by
      count (0-5)
    - ``off_aces_scores`` - subscore for number of off-aces in the hand, indexed by count
      (0-3)
    - ``voids_scores`` - subscore for number of void suits in the hand, indexed by count
      (0-3)
    - ``scoring_coeff`` - array of coefficients to be multipled by the corresponding
      subscores (as described above) for their contribution to the overall hand strength
      score

    Normalization for trump and off-suit subscores means dividing the aggregate card value
    by the total number of points available for the category.  Thus, if the trump holding
    for the suit under consideration is L-K-10, the sum (based on lookup) is 7 + 2 + 0 =
    9, which is then divided by the total available points (24 in this case), before being
    multiplied by the ``trump_score`` coefficient.  For off-suits, only the highest
    normalized suit value is mulitplied by the ``max_suit_score`` coefficient.

    The weighted subscores are added together to yield the overall hand strengh score used
    by ``StrategySmart``.  Note that the set of scoring coefficients don't have to add up
    to 100, but specifying it thus makes it easier to understand the relative weighting
    between the scoring components.

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
            setattr(self, key, kwargs.get(key) if key in kwargs else base_value)
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

    def hand_strength(self, trump_suit: Suit, comp_vals: dict = None) -> float:
        """Return the overall hand strength score given a trump suit context, based on
        parameters and multiplier coefficients specified for the instance (base config
        plus constructor overrides).  If ``comp_vals`` is specified (as a dict), the
        contribution from the individual components will be written to it as a
        StrengthTuple (see above), indexed by score name.
        """
        # KINDA HACKY: local variables need to align with keys in `self.scoring_coeff`
        # (enforced by the assert in the loop, below)
        trump_score = None
        suit_scores = []  # no need to track associated suits, for now
        sub_strengths = {}

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
            score_value = raw_value * coeff
            sub_strengths[score] = (score_value, raw_value, coeff)  # StrengthTuple
            log.debug(f"  {score:15}: {score_value:6.2f} ({raw_value:.2f} * {coeff:d})")
            strength += score_value
        log.debug(f"{'hand_strength':15}: {strength:6.2f}")
        if isinstance(comp_vals, dict):
            comp_vals.update(sub_strengths)
        return strength
