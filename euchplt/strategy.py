#!/usr/bin/env python
# -*- coding: utf-8 -*-

from enum import Enum
from typing import Optional
from random import Random
from importlib import import_module

from .core import ConfigError, LogicError, cfg, log
from .card import SUITS, Suit, Rank, Card, right, ace, jack
from .euchre import Bid, PASS_BID, NULL_BID, defend_suit, Hand, Trick, DealState
from .analysis import SUIT_CTX, HandAnalysis, PlayAnalysis

############
# Strategy #
############

def get_strategy(strat_name: str) -> 'Strategy':
    """Return instantiated Strategy object based on configured strategy, identified
    by name; note that the named strategy entry may override base parameter values
    specified for the underlying implementation class
    """
    strategies = cfg.config('strategies')
    if strat_name not in strategies:
        raise RuntimeError(f"Strategy '{strat_name}' is not known")
    strat_info   = strategies[strat_name]
    class_name   = strat_info.get('base_class')
    module_path  = strat_info.get('module_path')
    strat_params = strat_info.get('strategy_params') or {}
    if not class_name:
        raise ConfigError(f"'base_class' not specified for strategy '{strat_name}'")
    if module_path:
        module = import_module(module_path)
        strat_class = getattr(module, class_name)
    else:
        strat_class = globals()[class_name]

    return strat_class(**strat_params)

class Strategy:
    """
    """
    def __init__(self, **kwargs):
        """Note that kwargs are parameters overrides on top of base_strategy_params
        (in the config file) for the underlying implementation class
        """
        cls_name = type(self).__name__
        base_params = cfg.config('base_strategy_params')
        if cls_name not in base_params:
            raise ConfigError(f"Strategy class '{cls_name}' does not exist")
        for key, base_value in base_params[cls_name].items():
            setattr(self, key, kwargs.get(key) or base_value)
        pass  # TEMP: for debugging!!!

    def __str__(self):
        return self.__class__.__name__

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """
        """
        raise NotImplementedError("Can't call abstract method")

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called
        """
        raise NotImplementedError("Can't call abstract method")

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """
        """
        raise NotImplementedError("Can't call abstract method")

##################
# StrategyRandom #
##################

class StrategyRandom(Strategy):
    """
    """
    seed:   Optional[int] = None
    random: Random

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.random = Random(self.seed)

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        if def_bid:
            alone = self.random.random() < 0.10
            return Bid(defend_suit, alone)

        bid_no = len(deal.bids)
        do_bid = self.random.random() < 1 / (9 - bid_no)
        if do_bid:
            if deal.bid_round == 1:
                alone = self.random.random() < 0.10
                return Bid(deal.turn_card.suit, alone)
            else:
                alone = self.random.random() < 0.20
                biddable_suits = [s for s in SUITS if s != deal.turn_card.suit]
                return Bid(self.random.choice(biddable_suits), alone)
        else:
            return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return self.random.choice(deal.hand.cards)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return self.random.choice(valid_plays)

##################
# StrategySimple #
##################

class StrategySimple(Strategy):
    """Represents minimum logic for passable play, very basic strategy, fairly
    conservative (though we add an `aggressive` option)
    """
    aggressive: bool = False

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        analysis   = HandAnalysis(deal.hand)
        turn_suit  = deal.turn_card.suit
        bid_suit   = None
        alone      = False
        num_trump  = None
        off_aces   = None
        num_bowers = None

        if def_bid:
            # defend alone if 4 or more trump, or 3 trump and off-ace
            num_trump = len(analysis.trump_cards(deal.contract.suit))
            off_aces  = analysis.off_aces(deal.contract.suit)
            if num_trump >= 4 or (num_trump == 3 and len(off_aces) > 0):
                alone = True
            return Bid(defend_suit, alone)

        if deal.bid_round == 1:
            # bid if 3 or more trump, and bower/off-ace
            num_trump  = len(analysis.trump_cards(turn_suit))
            off_aces   = analysis.off_aces(turn_suit)
            num_bowers = len(analysis.bowers(turn_suit))
            if deal.is_dealer:
                num_trump += 1
                if deal.turn_card.rank == jack:
                    num_bowers += 1
                if num_trump >= 2 and len(off_aces) > 0:
                    bid_suit = turn_suit
            elif num_trump >= 3 and (off_aces or num_bowers > 0):
                bid_suit = turn_suit
        else:
            assert deal.bid_round == 2
            # bid if 3 or more trump in any suit, and bower/off-ace
            for suit in SUITS:
                if suit == turn_suit:
                    continue
                num_trump  = len(analysis.trump_cards(suit))
                off_aces   = analysis.off_aces(suit)
                num_bowers = len(analysis.bowers(suit))
                if num_trump >= 3 and (off_aces or num_bowers > 0):
                    bid_suit = suit
                    break

        if bid_suit:
            assert num_trump is not None
            assert off_aces is not None
            assert num_bowers is not None
            # go alone if 4 or more trump, or 3 trump and off-ace; must have at least
            # one bower (right may be buried, so not required)
            if num_trump >= 4 and num_bowers > 0:
                alone = True
            elif num_trump == 3 and num_bowers > 0 and off_aces:
                alone = True
            return Bid(bid_suit, alone)

        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        analysis = PlayAnalysis(deal)
        by_level = analysis.cards_by_level(offset_trump=True)
        return by_level[-1]

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        analysis = PlayAnalysis(deal)
        by_level = analysis.cards_by_level(offset_trump=True)

        # lead highest card
        if deal.play_seq == 0:
            for card in by_level:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        lead_card = trick.plays[0][1]
        follow_cards = analysis.follow_cards(lead_card)

        # partner is winning, try and duck (unless `aggressive` third hand)
        if trick.winning_pos == deal.pos ^ 0x02:
            take_order = 1 if (self.aggressive and deal.play_seq == 2) else -1
            cards = follow_cards if follow_cards else by_level
            for card in cards[::take_order]:
                if card in valid_plays:
                    return card
            raise LogicError("No valid card to play")

        # opponents winning, take trick if possible
        cards = follow_cards if follow_cards else by_level
        # second/third hand take low unless `aggressive` specified (fourth
        # hand always take low)
        take_order = 1 if (self.aggressive and deal.play_seq < 3) else -1
        for card in cards[::take_order]:
            if card in valid_plays and card.beats(trick.winning_card, trick):
                return card
        # can't take, so just duck or slough off
        for card in cards[::-1]:
            if card in valid_plays:
                return card
        raise LogicError("No valid card to play")

#################
# StrategySmart #
#################

class HandAnalysisSmart(HandAnalysis):
    """Example parameter values (current defaults in config.yml):

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

    def __init__(self, hand: Hand, params: dict = None):
        super().__init__(hand)
        params = params or {}
        cls_name = type(self).__name__
        base_params = cfg.config('base_analysis_params')
        if cls_name not in base_params:
            raise ConfigError(f"Analysis class '{cls_name}' does not exist")
        for key, base_value in base_params[cls_name].items():
            setattr(self, key, params.get(key) or base_value)
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
        log.info(f"hand: {self.hand} (trump: {trump_suit})")
        for score, coeff in self.scoring_coeff.items():
            raw_value = locals()[score]
            assert isinstance(raw_value, float)
            score_value = locals()[score] * coeff
            log.info(f"  {score:15}: {score_value:6.2f} ({raw_value:.2f} * {coeff:d})")
            strength += score_value
        log.info(f"{'hand_strength':15}: {strength:6.2f}")
        return strength

    def turn_card_rank(self, turn_card: Card) -> Rank:
        """SUPER-HACKY: this doesn't really belong here, need to figure out a nicer way
        of doing this!!!
        """
        ctx = SUIT_CTX[turn_card.suit]
        return turn_card.effcard(ctx).rank

class PlayPlan(Enum):
    DRAW_TRUMP     = "Draw_Trump"
    PRESERVE_TRUMP = "Preserve_Trump"

class StrategySmart(Strategy):
    """Strategy based on rule-based scoring/strength assessments, both for
    bidding and playing.  The rules are parameterized, so variations can be
    specified in the config file.

    FUTURE: there is an opportunity to build a framework for optimizing the
    various parameters, either in an absolute sense, or possibly relative to
    different opponent profiles.
    """
    hand_analysis:    dict
    turn_card_value:  list[int]  # by rank.idx
    turn_card_coeff:  list[int]  # by pos (0-3)
    bid_thresh:       list[int]  # by pos (0-7)
    alone_margin:     list[int]  # by pos (0-7)
    def_alone_thresh: list[int]  # by pos (0-7)

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """General logic:
        round 1:
          - non-dealer:
            - compute hand strength for turn suit
            - adjust for turn card (partner vs. opp)
            - bid if strength > round1_thresh (by position)
          - dealer:
            - compute strength for turn suit + each possible discard
              (including turn card)
            - bid if max(strength) > round1_thresh (dealer position)
        round 2:
          - all players:
            - compute strength for each non-turn suit
            - bid if max(strength) > round2_thresh (by position)
        loners:
          - go alone if strength exceeds threshold by specified margin parameter
          - defend alone if strength (for contract suit) > def_alone_thresh
        """
        persist       = deal.player_state
        bid_pos       = deal.pos + (deal.bid_round - 1) * 4
        turn_suit     = deal.turn_card.suit
        bid_suit      = None
        strength      = None
        thresh_margin = None
        alone         = False

        if def_bid:
            if deal.is_partner_caller:
                # generally shouldn't get here, but just in case...
                return NULL_BID
            analysis = HandAnalysisSmart(deal.hand, self.hand_analysis)
            strength = analysis.hand_strength(deal.contract.suit)
            if strength > self.def_alone_thresh[bid_pos]:
                alone = True
                log.debug(f"Defending on hand strength of {strength:.2f}")
            return Bid(defend_suit, alone)

        if deal.bid_round == 1:
            if deal.is_dealer:
                strengths: list[tuple[Card, float]] = []
                for card in deal.hand:
                    hand = deal.hand.copy()
                    hand.remove_card(card)
                    hand.append_card(deal.turn_card)
                    analysis = HandAnalysisSmart(hand, self.hand_analysis)
                    strengths.append((card, analysis.hand_strength(turn_suit)))
                strengths.sort(key=lambda t: t[1], reverse=True)
                if strengths[0][1] > self.bid_thresh[bid_pos]:
                    discard, strength = strengths[0]
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = turn_suit
                    persist['discard'] = discard
                    log.debug(f"Dealer bidding based on discard of {strengths[0][0]}")
            else:
                analysis = HandAnalysisSmart(deal.hand, self.hand_analysis)
                strength = analysis.hand_strength(turn_suit)
                # make adjustment for turn card (up/down for partner/opp.)
                turn_rank = analysis.turn_card_rank(deal.turn_card)
                turn_value = self.turn_card_value[turn_rank.idx] / sum(self.turn_card_value)
                turn_strength = turn_value * self.turn_card_coeff[bid_pos]
                strength += turn_strength * (1.0 if deal.is_partner_dealer else -1)
                log.info(f"{'turn card adj':15}: "
                         f"{'+' if deal.is_partner_dealer else '-'}{turn_strength:.2f}")
                log.info(f"{'adj_strength':15}: {strength:6.2f}")
                if strength > self.bid_thresh[bid_pos]:
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = turn_suit
        else:
            assert deal.bid_round == 2
            analysis = HandAnalysisSmart(deal.hand, self.hand_analysis)
            for suit in SUITS:
                if suit == turn_suit:
                    continue
                strength = analysis.hand_strength(suit)
                if strength > self.bid_thresh[bid_pos]:
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = suit
                    break

        if bid_suit:
            assert thresh_margin is not None
            persist['strength'] = strength
            persist['thresh_margin'] = thresh_margin
            log.debug(f"Bidding on hand strength of {strength:.2f}")
            if thresh_margin > self.alone_margin[bid_pos]:
                alone = True
            return Bid(bid_suit, alone)

        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called

        possible future logic (first successful tactic):
          - all trump case (discard lowest)
          - create void
            - don't discard singleton ace (exception case?)
            - prefer next or green suit?
            - "always void next if loner called from pos 2"[???]
          - create doubleton
            - perhaps only do if high card in suit is actually viable (>=Q)
          - discard from next
            - don't unguard doubleton king or break up A-K
          - discard lowest
            - avoid unguarding doubleton king, while making sure that A-K doubleton
              takes precedence (if also present)
            - worry about off-ace vs. low trump?
            - choose between green suit doubletons?
        """
        assert deal.turn_card in deal.hand
        turn_suit = deal.turn_card.suit
        persist = deal.player_state

        # see if best discard was previously computed
        discard = persist.get('discard')
        if not discard:
            # REVISIT: for now, just use the same hand strength calculation used for
            # bidding; but LATER we may want to implement a more detailed rule-based
            # logic as documented above
            strengths: list[tuple[Card, float]] = []
            for card in deal.hand:
                hand = deal.hand.copy()
                hand.remove_card(card)
                analysis = HandAnalysisSmart(hand, self.hand_analysis)
                strengths.append((card, analysis.hand_strength(turn_suit)))
            strengths.sort(key=lambda t: t[1], reverse=True)
            discard, strength = strengths[0]
            log.debug(f"Dealer discard based on max strength of {strength:.2f}")
        elif discard not in deal.hand:
            raise LogicError(f"{discard} not available to discard in hand ({deal.hand})")

        return discard

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """
        """
        persist = deal.player_state
        if 'play_plan' not in persist:
            persist['play_plan'] = set()
        play_plan = persist['play_plan']

        analysis        = PlayAnalysis(deal)
        # in current hand
        trump_cards     = analysis.trump_cards()
        off_aces        = analysis.off_aces()
        singleton_cards = analysis.singleton_cards()
        my_winners      = analysis.my_winners()
        # across all hands
        trumps_played   = analysis.trumps_played()
        trumps_missing  = analysis.trumps_missing()  # not in current hand or played

        ###################
        # lead card plays #
        ###################

        def lead_last_card() -> Optional[Card]:
            if len(deal.hand) == 1:
                log.debug("Lead last card")
                return deal.hand.cards[0]

        def next_call_lead() -> Optional[Card]:
            """Especially if calling with weaker hand...

            * The best first lead on a next call is a small trump, this is especially
              true if you hold an off-suit Ace. By leading a small trump you stand the
              best chance of hitting your partner's hand. Remember, the odds are that
              he will have at least one bower in his hand
            * Leading the right may not be the best move. Your partner may only have
              one bower in his hand and you don't want them to clash. When you are
              holding a right/ace combination it's usually best to lead the ace. If
              the other bower has been turned down, then it is okay to lead the right.
            * In a hand where you only hold two small cards in next but no power, try
              leading an off suit that you think your partner may be able to trump.
              You may need the trump to make your point.
            * If your partner calls next and leads a trump, DO NOT lead trump back.
            """
            if deal.is_next_call and trump_cards:
                if not analysis.bowers():
                    log.debug("No bower, lead small trump")
                    play_plan.add(PlayPlan.PRESERVE_TRUMP)
                    return trump_cards[-1]
                elif len(trump_cards) > 1:
                    if trump_cards[0].rank == right and trump_cards[1].rank == ace:
                        log.debug("Lead ace from right-ace")
                        play_plan.add(PlayPlan.DRAW_TRUMP)
                        return trump_cards[1]
                    if trump_cards[0].level < ace.level:
                        suit_cards = analysis.green_suit_cards()
                        if suit_cards[0]:
                            log.debug("Lead low from longest green suit")
                            play_plan.add(PlayPlan.DRAW_TRUMP)
                            return suit_cards[0][-1]

        def draw_trump() -> Optional[Card]:
            """Draw trump if caller (strong hand), or flush out bower
            """
            if deal.is_caller and trumps_missing:
                if PlayPlan.DRAW_TRUMP in play_plan:
                    if len(trump_cards) > 2:
                        log.debug("Continue drawing trump")
                        return trump_cards[0]
                    elif len(trump_cards) >= 2:
                        log.debug("Last round of drawing trump")
                        play_plan.remove(PlayPlan.DRAW_TRUMP)
                        return trump_cards[0]
                elif len(trump_cards) >= 3:
                    play_plan.add(PlayPlan.DRAW_TRUMP)
                    log.debug("Draw trump (or flush out bower)")
                    return trump_cards[0]

        def lead_off_ace() -> Optional[Card]:
            """Off-ace (short suit, or green if defending?)
            """
            if off_aces:
                # TODO: choose more wisely if more than one, or possibly preserve ace to
                # avoid being trumped!!!
                if len(off_aces) == 1:
                    log.debug("Lead off-ace")
                    return off_aces[0]
                else:
                    log.debug("Lead off-ace (random choice)")
                    return random.choice(off_aces)

        def lead_to_partner_call() -> Optional[Card]:
            """No trump seen with partner as caller
            """
            if deal.is_partner_caller:
                if trump_cards and not trumps_played:
                    if analysis.bowers():
                        log.debug("Lead bower to partner's call")
                        return trump_cards[0]
                    elif len(trump_cards) > 1:
                        log.debug("Lead low trump to partner's call")
                        return trump_cards[-1]
                    elif singleton_cards:
                        # REVISIT: not sure we should do this, but if so, add some logic
                        # for choosing if more than one singleton!!!
                        if len(singleton_cards) == 1:
                            log.debug("Lead singleton to void suit")
                            return singleton_cards[0]
                        else:
                            log.debug("Lead singleton to void suit (random choice)")
                            return random.choice(singleton_cards)

        def lead_to_create_void() -> Optional[Card]:
            """If trump in hand, try and void a suit
            """
            if trump_cards and singleton_cards:
                # REVISIT: perhaps only makes sense in earlier rounds (2 and 3), and otherwise
                # add some logic for choosing if more than one singleton!!!
                if len(singleton_cards) == 1:
                    log.debug("Lead singleton to void suit")
                    return singleton_cards[0]
                else:
                    log.debug("Lead singleton to void suit (random choice)")
                    return random.choice(singleton_cards)

        def lead_suit_winner() -> Optional[Card]:
            """Try to lead winner (non-trump)
            """
            if my_winners:
                log.debug("Try and lead suit winner")
                # REVISIT: is this the right logic (perhaps makes no sense if preceded by
                # off-ace rule)???  Should also examine remaining cards in suit!!!
                return my_winners[0] if deal.trick_num <= 3 else my_winners[-1]

        def lead_low_non_trump() -> Optional[Card]:
            """If still trump in hand, lead lowest card (non-trump)
            """
            if trump_cards and len(trump_cards) < len(deal.hand):
                # NOTE: will pick suit by random if multiple cards at min level
                by_level = analysis.cards_by_level(offset_trump=True)
                log.debug("Lead lowest non-trump")
                return by_level[-1]

        def lead_low_from_long_suit() -> Optional[Card]:
            """Lead low from long suit (favor green if defending?)

            Note: always returns value, can be last in ruleset
            """
            suit_cards: list[list[Card]] = list(analysis.get_suit_cards().values())
            # cards already sorted (desc) within each suit
            suit_cards.sort(key=lambda s: len(s), reverse=True)
            # TODO: a little more logic in choosing suit (perhaps avoid trump, if possible)!!!
            log.debug("Lead low from longest suit")
            return suit_cards[0][0]

        def lead_random_card() -> Optional[Card]:
            """This is a catch-all, though we should look at cases where this happens
            and see if there is a better rule to insert before it

            Note: always returns value, can be last in ruleset
            """
            log.debug("Lead random card")
            return random.choice(valid_plays)

        #####################
        # follow card plays #
        #####################

        lead_card = deal.cur_trick.lead_card
        follow_cards = analysis.follow_cards(lead_card) if lead_card else None

        def play_last_card() -> Optional[Card]:
            """
            """
            if len(deal.hand) == 1:
                log.debug("Play last card")
                return deal.hand.cards[0]

        def follow_suit_low() -> Optional[Card]:
            """Follow suit low
            """
            if follow_cards:
                # REVISIT: are there cases where we want to try and take the lead???
                log.debug("Follow suit low")
                return follow_cards[-1]

        def throw_off_to_create_void() -> Optional[Card]:
            """Create void (if early in deal).  NOTE: this only matters if we've decided not
            to trump (e.g. to preserve for later)
            """
            if trump_cards and singleton_cards:
                if len(singleton_cards) == 1:
                    log.debug("Throw off singleton to void suit")
                    return singleton_cards[0]
                else:
                    # REVISIT: perhaps only makes sense in earlier rounds (2 and 3), and also
                    # reconsider selection if multiple (currently lowest valued)!!!
                    singleton_cards.sort(key=lambda c: c.efflevel(trick), reverse=True)
                    log.debug("Throw off singleton to void suit (lowest)")
                    return singleton_cards[-1]

        def throw_off_low() -> Optional[Card]:
            """Throw off lowest non-trump card
            """
            if len(trump_cards) < len(deal.hand):
                # NOTE: this will pick random suit if multiple cards at min level
                by_level = analysis.cards_by_level(offset_trump=True)
                log.debug("Throw-off lowest non-trump")
                return by_level[-1]

        def play_low_trump() -> Optional[Card]:
            """Play lowest trump (assumes no non-trump remaining)
            """
            if trump_cards and len(trump_cards) == len(deal.hand):
                # REVISIT: are there cases where we want to play a higher trump???
                log.debug("Play lowest trump")
                return trump_cards[-1]

        def follow_suit_high() -> Optional[Card]:
            """Follow suit (high if can lead trick, low otherwise)
            """
            if follow_cards:
                if deal.lead_trumped:
                    log.debug("Follow suit low (trumped)")
                    return follow_cards[-1]
                if follow_cards[0].beats(trick.winning_card, trick):
                    # REVISIT: are there cases where we don't want to try and take the trick,
                    # or not play???
                    if deal.play_seq == 3:
                        for card in follow_cards[::-1]:
                            if card.beats(trick.winning_card, trick):
                                log.debug("Follow suit, take winner")
                                return card
                    else:
                        log.debug("Follow suit high")
                        return follow_cards[0]

                log.debug("Follow suit low (can't beat)")
                return follow_cards[-1]

        def trump_low() -> Optional[Card]:
            """Trump (low) to lead trick
            """
            if trump_cards:
                if deal.lead_trumped:
                    if trump_cards[0].beats(trick.winning_card, trick):
                        # REVISIT: are there cases where we don't want to try and take the trick,
                        # or not play???
                        if deal.play_seq == 3:
                            for card in trump_cards:
                                if card.beats(trick.winning_card, trick):
                                    log.debug("Overtrump, take winner")
                                    return card
                        else:
                            log.debug("Overtrump high")
                            return trump_cards[0]
                else:
                    # hold onto highest remaining trump (sure winner later), otherwise try and
                    # take the trick
                    # REVISIT: are there cases where we want to play a higher trump, or other
                    # reasons to throw off (esp. if pos == 1 and partner yet to play)???
                    if len(trump_cards) > 1:
                        log.debug("Play lowest trump, to lead trick")
                        return trump_cards[-1]
                    high_trump = analysis.suit_winners()[trick.trump_suit]
                    assert high_trump  # must exist, since we have one
                    if not trump_cards[0].same_as(high_trump, trick):
                        log.debug("Play last trump, to lead trick")
                        return trump_cards[0]

        def play_random_card() -> Optional[Card]:
            """This is a catch-all, though we should look at cases where this happens
            and see if there is a better rule to insert before it

            Note: always returns value, can be last in ruleset
            """
            log.debug("Lead random card")
            return random.choice(valid_plays)

        #############
        # rule sets #
        #############

        # Note, these are static for now, but later could be created dynamically based
        # on game or deal scenario
        init_lead    = [next_call_lead,
                        draw_trump,
                        lead_off_ace,
                        lead_to_partner_call,
                        lead_to_create_void,
                        lead_low_from_long_suit]

        subseq_lead  = [lead_last_card,
                        draw_trump,
                        # maybe swap the next two...
                        lead_to_partner_call,
                        lead_off_ace,
                        lead_suit_winner,
                        lead_to_create_void,
                        lead_low_non_trump,
                        lead_low_from_long_suit]

        part_winning = [play_last_card,
                        follow_suit_low,
                        throw_off_to_create_void,
                        throw_off_low,
                        play_low_trump,
                        play_random_card]

        opp_winning  = [play_last_card,
                        follow_suit_high,
                        trump_low,
                        throw_off_to_create_void,
                        throw_off_low,
                        play_random_card]

        #########################
        # pick ruleset and play #
        #########################

        def apply(ruleset):
            """REVISIT: perhaps genericize the ruleset thing, in which case
            we would move it to `core` or `utils` module
            """
            result = None
            for rule in ruleset:
                result = rule()
                if result:
                    break
            if not result:
                raise LogicError("Ruleset did not produce valid result ({ruleset})")
            return result

        if deal.play_seq == 0:
            ruleset = init_lead if deal.trick_num == 1 else subseq_lead
        else:
            ruleset = part_winning if deal.partner_winning else opp_winning

        card = apply(ruleset)
        return card.realcard(trick)

##############
# StrategyML #
##############

class StrategyML(Strategy):
    """
    """
    pass

########
# main #
########

import sys
import random
import time

from .core import dbg_hand

from .card import get_deck

def tune_strategy_smart(*args) -> int:
    """Run through a deck of cards evaluating the strength of each hand "dealt",
    iterating over the four suits as trump.  This is used for manual inspection
    to help tune the `HandAnalysisSmart` parameters and biddable thresholds.

    FUTURE: it would be cool to create an interactive utility whereby the human
    evaluates a number of hands based on biddability, as well as absolute and/or
    relative hand assessments, and a fitting algorithm determines the full set of
    parameters implied by the end-user input.
    """
    HAND_CARDS = 5
    seed = int(args[0]) if args else int(time.time()) % 1000000
    random.seed(seed)

    log.addHandler(dbg_hand)
    log.info(f"random.seed({seed})")

    deck = get_deck()
    while len(deck) >= HAND_CARDS:
        cards = deck[0:HAND_CARDS]
        cards.sort(key=lambda c: c.sortkey)
        analysis = HandAnalysisSmart(Hand(cards))
        for suit in SUITS:
            _ = analysis.hand_strength(suit)
        del deck[0:HAND_CARDS]

    return 0

def main() -> int:
    """Built-in driver to invoke various utility functions for the module

    Usage: strategy.py <func_name> [<arg> ...]

    Functions/usage:
      - tune_strategy_smart [<seed>]
    """
    if len(sys.argv) < 2:
        print(f"Utility function not specified", file=sys.stderr)
        return -1
    elif sys.argv[1] not in globals():
        print(f"Unknown utility function '{sys.argv[1]}'", file=sys.stderr)
        return -1

    util_func = globals()[sys.argv[1]]
    util_args = sys.argv[2:]
    return util_func(*util_args)

if __name__ == '__main__':
    sys.exit(main())
