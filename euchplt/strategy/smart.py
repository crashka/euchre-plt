# -*- coding: utf-8 -*-

from enum import Enum
from typing import ClassVar, Optional
from random import Random

from ..core import ConfigError, LogicError, log
from ..card import SUITS, Card, right, ace
from ..euchre import Bid, PASS_BID, NULL_BID, defend_suit, Trick, DealState
from ..analysis import HandAnalysisSmart, PlayAnalysis
from .base import Strategy

#################
# StrategySmart #
#################

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
    rand_seed:        Optional[int]
    random:           Random
    hand_analysis:    dict
    # bid parameters
    turn_card_value:  list[int]  # by rank.idx
    turn_card_coeff:  list[int]  # by pos (0-3)
    bid_thresh:       list[int]  # by pos (0-7)
    alone_margin:     list[int]  # by pos (0-7)
    def_alone_thresh: list[int]  # by pos (0-7)
    # play parameters
    init_lead:        list[str]
    subseq_lead:      list[str]
    part_winning:     list[str]
    opp_winning:      list[str]

    RULESETS: ClassVar[tuple[str, ...]] = ('init_lead', 'subseq_lead',
                                           'part_winning', 'opp_winning')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.random = Random(self.rand_seed)
        self.hand_analysis = self.hand_analysis or {}
        # do a cursory validation of the method names within the rulesets
        # for `play_cards()`; don't think we can "compile" them into real
        # function objects from here, so we'll have to do that at runtime
        # for now (unless/until we can get really clever about this)
        play_card_vars = set(self.__class__.play_card.__code__.co_varnames)
        for name in self.RULESETS:
            ruleset = getattr(self, name)
            if unknown := set(ruleset) - play_card_vars:
                raise ConfigError(f"Unknown method(s) '{', '.join(unknown)}' in ruleset '{name}'")

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
        bid_pos       = deal.bid_pos
        turn_suit     = deal.turn_card.suit
        bid_suit      = None
        strength      = None
        thresh_margin = None
        alone         = False

        if def_bid:
            if deal.is_partner_caller:
                # generally shouldn't get here, but just in case...
                return NULL_BID
            analysis = HandAnalysisSmart(deal.hand, **self.hand_analysis)
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
                    analysis = HandAnalysisSmart(hand, **self.hand_analysis)
                    strengths.append((card, analysis.hand_strength(turn_suit)))
                strengths.sort(key=lambda t: t[1], reverse=True)
                if strengths[0][1] > self.bid_thresh[bid_pos]:
                    discard, strength = strengths[0]
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = turn_suit
                    persist['discard'] = discard
                    log.debug(f"Dealer bidding based on discard of {strengths[0][0]}")
            else:
                analysis = HandAnalysisSmart(deal.hand, **self.hand_analysis)
                strength = analysis.hand_strength(turn_suit)
                # make adjustment for turn card (up/down for partner/opp.)
                turn_rank = analysis.turn_card_rank(deal.turn_card)
                turn_value = self.turn_card_value[turn_rank.idx] / sum(self.turn_card_value)
                turn_strength = turn_value * self.turn_card_coeff[bid_pos]
                strength += turn_strength * (1.0 if deal.is_partner_dealer else -1)
                log.debug(f"{'turn card adj':15}: "
                         f"{'+' if deal.is_partner_dealer else '-'}{turn_strength:.2f}")
                log.debug(f"{'adj_strength':15}: {strength:6.2f}")
                if strength > self.bid_thresh[bid_pos]:
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = turn_suit
        else:
            assert deal.bid_round == 2
            analysis = HandAnalysisSmart(deal.hand, **self.hand_analysis)
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
                analysis = HandAnalysisSmart(hand, **self.hand_analysis)
                strengths.append((card, analysis.hand_strength(turn_suit)))
            strengths.sort(key=lambda t: t[1], reverse=True)
            discard, strength = strengths[0]
            log.debug(f"Dealer discard based on max strength of {strength:.2f}")
        elif discard not in deal.hand:
            raise LogicError(f"{discard} not available to discard in hand ({deal.hand})")

        return discard

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """REVISIT: think about additional logic needed for going (or defending) alone,
        either in dynamic adjustment of rule traversal, or specifying new rulesets!!!
        """
        persist = deal.player_state
        if 'play_plan' not in persist:
            persist['play_plan'] = set()
        play_plan = persist['play_plan']

        analysis        = PlayAnalysis(deal)
        trump_cards     = analysis.trump_cards()
        singleton_cards = analysis.singleton_cards()

        ###################
        # lead card plays #
        ###################

        def lead_last_card() -> Optional[Card]:
            if len(deal.hand) == 1:
                log.debug("Lead last card")
                return deal.hand.cards[0]

        def next_call_lead() -> Optional[Card]:
            """Especially if calling with weaker hand...

            - The best first lead on a next call is a small trump, this is especially
              true if you hold an off-suit Ace. By leading a small trump you stand the
              best chance of hitting your partner's hand. Remember, the odds are that
              he will have at least one bower in his hand
            - Leading the right may not be the best move. Your partner may only have
              one bower in his hand and you don't want them to clash. When you are
              holding a right/ace combination it's usually best to lead the ace. If
              the other bower has been turned down, then it is okay to lead the right.
            - In a hand where you only hold two small cards in next but no power, try
              leading an off suit that you think your partner may be able to trump.
              You may need the trump to make your point.
            - If your partner calls next and leads a trump, DO NOT lead trump back.
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
            # perf note: defer call to `trumps_missing()`
            if deal.is_caller and analysis.trumps_missing():
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
            if off_aces := analysis.off_aces():
                # TODO: choose more wisely if more than one, or possibly preserve ace to
                # avoid being trumped!!!
                if len(off_aces) == 1:
                    log.debug("Lead off-ace")
                    return off_aces[0]
                else:
                    log.debug("Lead off-ace (random choice)")
                    return self.random.choice(off_aces)

        def lead_to_partner_call() -> Optional[Card]:
            """No trump seen with partner as caller
            """
            if deal.is_partner_caller:
                if trump_cards and not analysis.trumps_played():
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
                            return self.random.choice(singleton_cards)

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
                    return self.random.choice(singleton_cards)

        def lead_suit_winner() -> Optional[Card]:
            """Try to lead winner (non-trump)
            """
            if my_winners := analysis.my_winners():
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
            return self.random.choice(valid_plays)

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
            return self.random.choice(valid_plays)

        #############
        # rule sets #
        #############

        # Note, these are static for now (loaded from the config file), but later could
        # be created and/or adjusted dynamically based on match/game or deal scenario
        func_locals  = locals()
        init_lead    = [func_locals[rule] for rule in self.init_lead]
        subseq_lead  = [func_locals[rule] for rule in self.subseq_lead]
        part_winning = [func_locals[rule] for rule in self.part_winning]
        opp_winning  = [func_locals[rule] for rule in self.opp_winning]

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
