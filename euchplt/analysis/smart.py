# -*- coding: utf-8 -*-

from ..core import ConfigError, cfg, log
from ..card import SUITS, Suit, Rank, Card
from ..euchre import Hand
from .base import SUIT_CTX, HandAnalysis

#####################
# HandAnalysisSmart #
#####################

class HandAnalysisSmart(HandAnalysis):
    """Example parameter values (current defaults in config.yml)::

      trump_values     = [0, 0, 0, 1, 2, 4, 7, 10]
      suit_values      = [0, 0, 0, 1, 5, 10]
      num_trump_scores = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
      off_aces_scores  = [0.0, 0.2, 0.5, 1.0]
      voids_scores     = [0.0, 0.3, 0.7, 1.0] (index capped by number of trump)

      scoring_coeff    = {'trump_score':     40,
                          'max_suit_score':  10,
                          'num_trump_score': 20,
                          'off_aces_score':  15,
                          'voids_score':     15}

    hand scoring aspects (multiply by coefficients):

    - trump strength (add card values)
    - max off-suit strength (same)
    - num trump
    - off-aces
    - voids
    """
    # the following annotations represent the parameters that are specified
    # in the config file for the class name under `base_analysis_params`
    # (and which may be overridden under a `hand_analysis` parameter for
    # a parent strategy's configuration)
    trump_values:     list[int]
    suit_values:      list[int]
    num_trump_values: list[float]
    off_aces_values:  list[float]
    voids_values:     list[float]
    scoring_coeff:    dict[str, int]

    def __init__(self, hand: Hand, **kwargs):
        super().__init__(hand)
        class_name = type(self).__name__
        base_params = cfg.config('base_analysis_params')
        if class_name not in base_params:
            raise ConfigError(f"Analysis class '{class_name}' does not exist")
        for key, base_value in base_params[class_name].items():
            setattr(self, key, kwargs.get(key) or base_value)
        pass  # TEMP: for debugging!!!

    def suit_strength(self, suit: Suit, trump_suit: Suit) -> float:
        """Note that this requires that jacks be replaced by BOWER cards (rank
        of `right` or `left`)
        """
        value_arr = self.trump_values if suit == trump_suit else self.suit_values
        tot_value = 0
        suit_cards = self.get_suit_cards(trump_suit)[suit]
        for card in suit_cards:
            tot_value += value_arr[card.rank.idx]
        return tot_value / sum(value_arr)

    def hand_strength(self, trump_suit: Suit) -> float:
        trump_score = None
        suit_scores = []  # no need to track associated suits, for now

        for suit in SUITS:
            if suit == trump_suit:
                trump_score = self.suit_strength(suit, trump_suit)
            else:
                suit_scores.append(self.suit_strength(suit, trump_suit))
        max_suit_score = max(suit_scores)
        assert isinstance(trump_score, float)
        assert isinstance(max_suit_score, float)

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
        """SUPER-HACKY: this doesn't really belong here, need to figure out a nicer way
        of doing this!!!
        """
        ctx = SUIT_CTX[turn_card.suit]
        return turn_card.effcard(ctx).rank
