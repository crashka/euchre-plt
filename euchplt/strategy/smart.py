# -*- coding: utf-8 -*-

from enum import Enum
from typing import ClassVar
from collections.abc import Callable
import random
import inspect

from ..core import ConfigError, LogicError, log
from ..card import Rank, SUITS, Card, right, ace
from ..euchre import Hand, Bid, PASS_BID, NULL_BID, defend_suit, Trick, DealState
from ..analysis import SUIT_CTX, HandAnalysisSmart, PlayAnalysis
from .base import Strategy

#############
# _PlayCard #
#############

class PlayPlan(Enum):
    """Strategy tags to persist within the ``_PlayCard`` state
    """
    DRAW_TRUMP     = "Draw_Trump"
    PRESERVE_TRUMP = "Preserve_Trump"

class _PlayCard:
    """Helper class for "smart" card playing tactics, which are implemented as individual
    methods that return a card to play (if determined within the tactic), or ``None`` (if
    tactic is not appropriate, by falling through the end of the method).

    An instance is instantiated for each call to ``StrategySmart.play_card()`` using the
    same call arguments.
    """
    deal:            DealState
    trick:           Trick
    valid_plays:     list[Card]

    play_plan:       set[PlayPlan]
    analysis:        PlayAnalysis
    trump_cards:     list[Card]
    singleton_cards: list[Card]

    def __init__(self, deal: DealState, trick: Trick, valid_plays: list[Card]):
        self.deal = deal
        self.trick = trick
        self.valid_plays = valid_plays

        persist = self.deal.player_state
        if 'play_plan' not in persist:
            persist['play_plan'] = set()
        self.play_plan = persist['play_plan']

        self.analysis        = PlayAnalysis(self.deal)
        self.trump_cards     = self.analysis.trump_cards()
        self.singleton_cards = self.analysis.singleton_cards()

    ###################
    # lead card plays #
    ###################

    def lead_last_card(self) -> Card | None:
        """All other lead tactics degenerate into this for final card (haha)
        """
        if len(self.deal.hand) == 1:
            log.debug("Lead last card")
            return self.deal.hand.cards[0]

    def next_call_lead(self) -> Card | None:
        """For next suit call, especially if calling with a weaker hand

        From https://ohioeuchre.com/E_next.php:

        - The best first lead on a next call is a small trump, this is especially
          true if you hold an off-suit Ace. By leading a small trump you stand the
          best chance of hitting your partner's hand. Remember, the odds are that
          he will have at least one bower in his hand.
        - Leading the right may not be the best move. Your partner may only have
          one bower in his hand and you don't want them to clash. When you are
          holding a right/ace combination it's usually best to lead the ace. If
          the other bower has been turned down, then it is okay to lead the right.
        - In a hand where you only hold two small cards in next but no power, try
          leading an off suit that you think your partner may be able to trump.
          You may need the trump to make your point.
        - If your partner calls next and leads a trump, DO NOT lead trump back.
        """
        if self.deal.is_next_call and self.trump_cards:
            if not self.analysis.bowers():
                log.debug("No bower, lead small trump")
                self.play_plan.add(PlayPlan.PRESERVE_TRUMP)
                return self.trump_cards[-1]
            elif len(self.trump_cards) > 1:
                if self.trump_cards[0].rank == right and self.trump_cards[1].rank == ace:
                    log.debug("Lead ace from right-ace")
                    self.play_plan.add(PlayPlan.DRAW_TRUMP)
                    return self.trump_cards[1]
                if self.trump_cards[0].level < ace.level:
                    suit_cards = self.analysis.green_suit_cards()
                    if suit_cards[0]:
                        log.debug("Lead low from longest green suit")
                        self.play_plan.add(PlayPlan.DRAW_TRUMP)
                        return suit_cards[0][-1]

    def draw_trump(self) -> Card | None:
        """Draw trump if caller (strong hand), or flush out bower
        """
        # perf note: defer call to `trumps_missing()`
        if self.deal.is_caller and self.analysis.trumps_missing():
            if PlayPlan.DRAW_TRUMP in self.play_plan:
                if len(self.trump_cards) > 2:
                    log.debug("Continue drawing trump")
                    return self.trump_cards[0]
                elif len(self.trump_cards) >= 2:
                    log.debug("Last round of drawing trump")
                    self.play_plan.remove(PlayPlan.DRAW_TRUMP)
                    return self.trump_cards[0]
            elif len(self.trump_cards) >= 3:
                self.play_plan.add(PlayPlan.DRAW_TRUMP)
                log.debug("Draw trump (or flush out bower)")
                return self.trump_cards[0]

    def lead_off_ace(self) -> Card | None:
        """Off-ace (short suit, or green if defending?)
        """
        if off_aces := self.analysis.off_aces():
            # TODO: choose more wisely if more than one, or possibly preserve ace to
            # avoid being trumped!!!
            if len(off_aces) == 1:
                log.debug("Lead off-ace")
                return off_aces[0]
            else:
                log.debug("Lead off-ace (random choice)")
                return random.choice(off_aces)

    def lead_to_partner_call(self) -> Card | None:
        """No trump seen with partner as caller
        """
        if self.deal.is_partner_caller:
            if self.trump_cards and not self.analysis.trumps_played():
                if self.analysis.bowers():
                    log.debug("Lead bower to partner's call")
                    return self.trump_cards[0]
                elif len(self.trump_cards) > 1:
                    log.debug("Lead low trump to partner's call")
                    return self.trump_cards[-1]
                elif self.singleton_cards:
                    # REVISIT: not sure we should do this, but if so, add some logic
                    # for choosing if more than one singleton!!!
                    if len(self.singleton_cards) == 1:
                        log.debug("Lead singleton to void suit")
                        return self.singleton_cards[0]
                    else:
                        log.debug("Lead singleton to void suit (random choice)")
                        return random.choice(self.singleton_cards)

    def lead_to_create_void(self) -> Card | None:
        """If trump in hand, try and void a suit
        """
        if self.trump_cards and self.singleton_cards:
            # REVISIT: perhaps only makes sense in earlier rounds (2 and 3), and otherwise
            # add some logic for choosing if more than one singleton!!!
            if len(self.singleton_cards) == 1:
                log.debug("Lead singleton to void suit")
                return self.singleton_cards[0]
            else:
                log.debug("Lead singleton to void suit (random choice)")
                return random.choice(self.singleton_cards)

    def lead_suit_winner(self) -> Card | None:
        """Try to lead winner (non-trump)
        """
        if my_winners := self.analysis.my_winners():
            log.debug("Try and lead suit winner")
            # REVISIT: is this the right logic (perhaps makes no sense if preceded by
            # off-ace rule)???  Should also examine remaining cards in suit!!!
            return my_winners[0] if self.deal.trick_num <= 3 else my_winners[-1]

    def lead_low_non_trump(self) -> Card | None:
        """If still trump in hand, lead lowest card (non-trump)
        """
        if self.trump_cards and len(self.trump_cards) < len(self.deal.hand):
            # NOTE: will pick suit by random if multiple cards at min level
            by_level = self.analysis.cards_by_level(offset_trump=True)
            log.debug("Lead lowest non-trump")
            return by_level[-1]

    def lead_low_from_long_suit(self) -> Card | None:
        """Lead low from long suit (favor green if defending?)

        Note: always returns value, can be last in a ruleset
        """
        suit_cards: list[list[Card]] = list(self.analysis.get_suit_cards().values())
        # cards already sorted (desc) within each suit
        suit_cards.sort(key=lambda s: len(s), reverse=True)
        # TODO: a little more logic in choosing suit (perhaps avoid trump, if possible)!!!
        log.debug("Lead low from longest suit")
        return suit_cards[0][0]

    def lead_random_card(self) -> Card | None:
        """This is a catch-all, though we should look at cases where this happens
        and see if there is a better rule to insert before it

        Note: always returns value, can be last in a ruleset
        """
        log.debug("Lead random card")
        return random.choice(self.valid_plays)

    #####################
    # follow card plays #
    #####################

    def play_last_card(self) -> Card | None:
        """All other play tactics degenerate into this for final card (haha)
        """
        if len(self.deal.hand) == 1:
            log.debug("Play last card")
            return self.deal.hand.cards[0]

    def follow_suit_low(self) -> Card | None:
        """Follow suit low
        """
        lead_card = self.deal.cur_trick.lead_card
        if lead_card and (follow_cards := self.analysis.follow_cards(lead_card)):
            # REVISIT: are there cases where we want to try and take the lead???
            log.debug("Follow suit low")
            return follow_cards[-1]

    def throw_off_to_create_void(self) -> Card | None:
        """Create void (if early in deal).  NOTE: this only matters if we've decided not
        to trump (e.g. to preserve for later)
        """
        if self.trump_cards and self.singleton_cards:
            if len(self.singleton_cards) == 1:
                log.debug("Throw off singleton to void suit")
                return self.singleton_cards[0]
            else:
                # REVISIT: perhaps only makes sense in earlier rounds (2 and 3), and also
                # reconsider selection if multiple (currently lowest valued)!!!
                self.singleton_cards.sort(key=lambda c: c.efflevel(self.trick), reverse=True)
                log.debug("Throw off singleton to void suit (lowest)")
                return self.singleton_cards[-1]

    def throw_off_low(self) -> Card | None:
        """Throw off lowest non-trump card
        """
        if len(self.trump_cards) < len(self.deal.hand):
            # NOTE: this will pick random suit if multiple cards at min level
            by_level = self.analysis.cards_by_level(offset_trump=True)
            log.debug("Throw-off lowest non-trump")
            return by_level[-1]

    def play_low_trump(self) -> Card | None:
        """Play lowest trump (assumes no non-trump remaining)
        """
        if self.trump_cards and len(self.trump_cards) == len(self.deal.hand):
            # REVISIT: are there cases where we want to play a higher trump???
            log.debug("Play lowest trump")
            return self.trump_cards[-1]

    def follow_suit_high(self) -> Card | None:
        """Follow suit (high if can lead trick, low otherwise)
        """
        lead_card = self.deal.cur_trick.lead_card
        if lead_card and (follow_cards := self.analysis.follow_cards(lead_card)):
            if self.deal.lead_trumped:
                log.debug("Follow suit low (trumped)")
                return follow_cards[-1]
            if follow_cards[0].beats(self.trick.winning_card, self.trick):
                # REVISIT: are there cases where we don't want to try and take the trick,
                # or not play???
                if self.deal.play_seq == 3:
                    for card in follow_cards[::-1]:
                        if card.beats(self.trick.winning_card, self.trick):
                            log.debug("Follow suit, take winner")
                            return card
                else:
                    log.debug("Follow suit high")
                    return follow_cards[0]

            log.debug("Follow suit low (can't beat)")
            return follow_cards[-1]

    def trump_low(self) -> Card | None:
        """Trump (low) to lead trick
        """
        if self.trump_cards:
            if self.deal.lead_trumped:
                if self.trump_cards[0].beats(self.trick.winning_card, self.trick):
                    # REVISIT: are there cases where we don't want to try and take the trick,
                    # or not play???
                    if self.deal.play_seq == 3:
                        for card in self.trump_cards:
                            if card.beats(self.trick.winning_card, self.trick):
                                log.debug("Overtrump, take winner")
                                return card
                    else:
                        log.debug("Overtrump high")
                        return self.trump_cards[0]
            else:
                # hold onto highest remaining trump (sure winner later), otherwise try and
                # take the trick
                # REVISIT: are there cases where we want to play a higher trump, or other
                # reasons to throw off (esp. if pos == 1 and partner yet to play)???
                if len(self.trump_cards) > 1:
                    log.debug("Play lowest trump, to lead trick")
                    return self.trump_cards[-1]
                high_trump = self.analysis.suit_winners()[self.trick.trump_suit]
                assert high_trump  # must exist, since we have one
                if not self.trump_cards[0].same_as(high_trump, self.trick):
                    log.debug("Play last trump, to lead trick")
                    return self.trump_cards[0]

    def play_random_card(self) -> Card | None:
        """This is a catch-all, though we should look at cases where this happens
        and see if there is a better rule to insert before it

        Note: always returns value, can be last in a ruleset
        """
        log.debug("Play random card")
        return random.choice(self.valid_plays)

#################
# StrategySmart #
#################

def get_methods(cls: type) -> dict[str, Callable]:
    """Utility function to return dict of user-defined methods for a class
    """
    meth_tuples = inspect.getmembers(cls, predicate=inspect.isfunction)
    return {x[0]: x[1] for x in meth_tuples if not x[0].startswith('__')}

class StrategySmart(Strategy):
    """Strategy based on rule-based scoring/strength assessments, both for bidding and
    playing.  The rules are parameterized, so variations can be specified in the config
    file.

    Bidding
    -------

    Example parameter values for bidding::

      hand_analysis:    # keep this empty here, but may be overridden by
                        # individual strategies
      turn_card_value:  [10, 15, 0, 20, 25, 30, 0, 50]
      turn_card_coeff:  [25, 25, 25, 25]
      bid_thresh:       [35, 35, 35, 35, 35, 35, 35, 35]
      alone_margin:     [10, 10, 10, 10, 10, 10, 10, 10]
      def_alone_thresh: [35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35]

    Brief description of bid parameters (see ``bid()`` for more information):

    - ``hand_analysis`` - override base config parameters for ``HandAnalysisSmart``
    - ``turn_card_value`` - value for turn card, indexed by rank (9-R, e.g. A = 30, above)
    - ``turn_card_coeff`` - multiplier for ``turn_card_value``, indexed by seat position
      (product to be added to hand strength)
    - ``bid_thresh`` - total strength needed to bid, indexed by bid position (across 2
      rounds)
    - ``alone_margin`` - margin above ``bid_thresh`` needed to go alone, indexed by bid
      positions
    - ``def_alone_thresh`` - total strength needed to defend alone, indexed by bid
      position

    FUTURE: there is an opportunity to build a framework for optimizing the various
    parameters, either in an absolute sense, or possibly relative to different opponent
    profiles.  In the mean time, see ``tune_strategy_smart()`` as a tool to aid in manual
    tuning.

    Playing
    -------

    Playing strategy is implemented using a number of individual play "tactics", or card
    selection criteria applicable to a particular circumstance and/or objective, which may
    or may not pertain to the current deal context.  These tactics are organized into
    "rulesets", which are lists of method calls that are tried in sequence until one of
    them returns a result (i.e. a card to play).  There are distinct rulesets for the
    following play situations within a deal:

    - Initial lead (first trick)
    - Subsequent leads
    - Partner winning (current trick)
    - Opponent winning (current trick)

    The rulesets are defined in the base_config.yml file (and overridable for individual
    strategies in strategies.yml).  Here is an excerpt from the base configuration::

      subseq_lead:
        - lead_last_card
        - draw_trump
        - lead_off_ace
        - lead_to_partner_call
        - lead_suit_winner
        - lead_to_create_void
        - lead_low_non_trump
        - lead_low_from_long_suit
      part_winning:
        - play_last_card
        - follow_suit_low
        - throw_off_to_create_void
        - throw_off_low
        - play_low_trump
        - play_random_card

    The methods that implement the play tactics are contained (and documented) in the
    ``_PlayCard`` class.  This class also maintains a "play plan" (with tags such as
    ``DRAW_TRUMP`` or ``PRESERVE_TRUMP``) that can be dynamically managed and helps
    direct the execution within the tactics.
    """
    hand_analysis:    dict
    ruleset:          dict[str, list[Callable]]
    # bid parameters
    turn_card_value:  list[int]  # by rank.idx
    turn_card_coeff:  list[int]  # by pos (0-3)
    bid_thresh:       list[int]  # by pos (0-7)
    alone_margin:     list[int]  # by pos (0-7)
    def_alone_thresh: list[int]  # by pos (0-10)
    # play parameters
    init_lead:        list[str]
    subseq_lead:      list[str]
    part_winning:     list[str]
    opp_winning:      list[str]

    play_methods:     ClassVar[dict[str, Callable]] = get_methods(_PlayCard)
    RULESETS:         ClassVar[tuple[str, ...]] = ('init_lead', 'subseq_lead',
                                                   'part_winning', 'opp_winning')

    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)
        self.hand_analysis = self.hand_analysis or {}
        self.ruleset = {}
        # do a cursory validation of the method names within the rulesets for
        # `play_cards()`
        method_names = set(self.play_methods.keys())
        for name in self.RULESETS:
            rule_names = getattr(self, name)
            if unknown := set(rule_names) - method_names:
                raise ConfigError(f"Unknown method(s) '{', '.join(unknown)}' in ruleset '{name}'")

        # Note, these are static for now (loaded from the config file), but later could
        # be created and/or adjusted dynamically based on match/game or deal scenario
        meths = self.play_methods
        self.ruleset['init_lead']    = [meths[rule] for rule in self.init_lead]
        self.ruleset['subseq_lead']  = [meths[rule] for rule in self.subseq_lead]
        self.ruleset['part_winning'] = [meths[rule] for rule in self.part_winning]
        self.ruleset['opp_winning']  = [meths[rule] for rule in self.opp_winning]

    def turn_card_rank(self, turn_card: Card) -> Rank:
        """HACKY: this doesn't really belong here, but we need ``rank.idx`` for the turn
        card (used as index into config file params) even though it shouldn't really be
        visible externally.  But this is better than polluting the ``Card`` interface.
        """
        ctx = SUIT_CTX[turn_card.suit]
        return turn_card.effcard(ctx).rank

    def get_turn_strength(self, deal: DealState, bid_pos: int) -> float:
        """Get the strength contribution (or penalty!) for the turn card (scaled to the
        overall hand strength), given the current deal context.  Value is positive or
        negative depending on whether partner or opponent (respectively) is the dealer.
        Note that this call is only valid for first round bidding from a non-dealer
        position.
        """
        turn_rank = self.turn_card_rank(deal.turn_card)
        turn_value = self.turn_card_value[turn_rank.idx] / sum(self.turn_card_value)
        turn_strength = turn_value * self.turn_card_coeff[bid_pos]
        return turn_strength * (1.0 if deal.is_partner_dealer else -1.0)

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """General logic:

        Round 1
        -------

        **Non-dealer**

        - Compute hand strength for turn suit
        - Adjust for turn card (partner vs. opp)
        - Bid if strength > round1_thresh (by position)

        **Dealer**

        - Compute strength for turn suit + each possible discard (including turn card)
        - Bid if max(strength) > round1_thresh (dealer position)

        Round 2
        -------

        **All players**

        - Compute strength for each non-turn suit
        - Bid if max(strength) > round2_thresh (by position)

        **Loners**

        - Go alone if strength exceeds threshold by specified margin parameter
        - Defend alone if strength > def_alone_thresh (for contract suit)
        """
        persist       = deal.player_state
        bid_pos       = deal.bid_pos
        turn_suit     = deal.turn_card.suit
        bid_suit      = None
        strength      = None
        thresh_margin = None
        turn_strength = None
        new_hand      = None
        alone         = False
        sub_strgths   = {}

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

        # only regular call bidding from here on down (see early exit above)
        if deal.bid_round == 1:
            if deal.is_dealer:
                # for each possible discard: (card, hard, strength, sub_strgths)
                strengths: list[tuple[Card, Hand, float, dict]] = []
                for card in deal.hand:
                    tmp_hand = deal.hand.copy()
                    tmp_hand.remove_card(card)
                    tmp_hand.append_card(deal.turn_card)
                    tmp_sub_strgths = {}
                    analysis = HandAnalysisSmart(tmp_hand, **self.hand_analysis)
                    tmp_strength = analysis.hand_strength(turn_suit, tmp_sub_strgths)
                    strengths.append((card, tmp_hand, tmp_strength, tmp_sub_strgths))
                strengths.sort(key=lambda t: t[2], reverse=True)
                if strengths[0][2] > self.bid_thresh[bid_pos]:
                    discard, new_hand, strength, sub_strgths = strengths[0]
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = turn_suit
                    persist['discard'] = discard
                    log.debug(f"Dealer bidding based on discard of {strengths[0][0]}")
            else:
                analysis = HandAnalysisSmart(deal.hand, **self.hand_analysis)
                strength = analysis.hand_strength(turn_suit, sub_strgths)
                # this call takes dealer position into account (partner or opponent)
                turn_strength = self.get_turn_strength(deal, bid_pos)
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
                strength = analysis.hand_strength(suit, sub_strgths)
                if strength > self.bid_thresh[bid_pos]:
                    thresh_margin = strength - self.bid_thresh[bid_pos]
                    bid_suit = suit
                    break

        if bid_suit:
            assert thresh_margin is not None
            persist['strength'] = strength
            persist['thresh_margin'] = thresh_margin
            if turn_strength is not None:
                persist['turn_strength'] = turn_strength
            if sub_strgths:
                persist['sub_strgths'] = sub_strgths
            if new_hand:
                persist['new_hand'] = new_hand
            log.debug(f"Bidding on hand strength of {strength:.2f}")
            if thresh_margin > self.alone_margin[bid_pos]:
                alone = True
            return Bid(bid_suit, alone)

        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """Note that the turn card is already in the player's hand (six cards now) when
        this is called

        Possible future logic (first successful tactic):

        - All trump case (discard lowest)
        - Create void

          - Don't discard singleton ace (exception case?)
          - Prefer next or green suit?
          - "Always void next if loner called from pos 2"[???]

        - Create doubleton

          - Perhaps only do if high card in suit is actually viable (>=Q)

        - Discard from next

          - Don't unguard doubleton king or break up A-K

        - Discard lowest

          - Avoid unguarding doubleton king, while making sure that A-K doubleton
            takes precedence (if also present)
          - Worry about off-ace vs. low trump?
          - Choose between green suit doubletons?
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
                tmp_hand = deal.hand.copy()
                tmp_hand.remove_card(card)
                analysis = HandAnalysisSmart(tmp_hand, **self.hand_analysis)
                strengths.append((card, analysis.hand_strength(turn_suit)))
            strengths.sort(key=lambda t: t[1], reverse=True)
            discard, strength = strengths[0]
            log.debug(f"Dealer discard based on max strength of {strength:.2f}")
        elif discard not in deal.hand:
            raise LogicError(f"{discard} not available to discard in hand ({deal.hand})")

        return discard

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See ``_PlayCard`` for all of the code for the various play tactics.  Rulesets
        are lists of ``PlayCard`` methods, which are called in sequence until one returns
        a "result" (i.e. a recommended card play).

        REVISIT: think about additional logic needed for going (or defending) alone,
        either in dynamic adjustment of rule traversal, or specifying new rulesets!!!
        """
        # pick the appropriate ruleset based on deal context
        if deal.play_seq == 0:
            ruleset = (self.ruleset['init_lead'] if deal.trick_num == 1
                       else self.ruleset['subseq_lead'])
        else:
            ruleset = (self.ruleset['part_winning'] if deal.partner_winning
                       else self.ruleset['opp_winning'])
        assert ruleset

        player = _PlayCard(deal, trick, valid_plays)
        result = None
        for rule in ruleset:
            result = rule(player)  # `rule` will be a `_PlayCard` method callable
            if result:
                break
        if not result:
            raise LogicError("Ruleset did not produce valid result ({ruleset})")

        card = result
        return card.realcard(trick)
