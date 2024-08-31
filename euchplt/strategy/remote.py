# -*- coding: utf-8 -*-

from enum import Enum, StrEnum

from requests import Session, HTTPError

from ..core import log
from ..card import SUITS, Card, CARDS, Deck
from ..euchre import null_suit, defend_suit, Bid, PASS_BID, Trick, DealState
from .base import Strategy, StrategyNotice

# can't import this from `deal`, so we just hardwire it here
DEALER_POS = 3

#########
# Enums #
#########

# direction of "travel" relative to us (e.g. for card mapping)
Dir = Enum('Dir', 'TO FROM')

class EpReq(StrEnum):
    """Note: the value for each member must correpond to a valid request type
    the the `requests` module.
    """
    GET      = "get"
    POST     = "post"
    PATCH    = "patch"

class EpPath(StrEnum):
    SESSION  = "/session"
    GAME     = "/game"
    DEAL     = "/deal"
    BID      = "/bid"
    SWAP     = "/swap"
    DEFNESE  = "/defense"
    TRICK    = "/trick"
    PLAY     = "/play"

class EpStatus(StrEnum):
    NEW      = "new"
    ACTIVE   = "active"
    UPDATE   = "update"
    COMPLETE = "complete"

# a couple of helpful aliases
EpActivate = (EpStatus.NEW, EpStatus.ACTIVE)
EpStatusT = EpStatus | tuple[EpStatus, EpStatus]

##################
# StrategyRemote #
##################

class StrategyRemote(Strategy):
    """Invocation of remote strategies through the `EuchreEndpoint`_ interface.

    NOTE: this subclass keeps state about the remote connection and session, so instances
    must be shared across partners.

    .. _EuchreEndpoint: https://github.com/crashka/EuchreEndpoint
    """
    # config parameters
    server_url:   str
    http_headers: dict[str, str]

    # `requests` stuff
    req_session:  Session

    # `EuchreEndpoint` stuff
    token:        str  # non-empty value indicates we have a session
    card_map:     list[int]
    suit_map:     list[int]
    card_rvmap:   list[int]
    suit_rvmap:   list[int]
    game_num:     int
    deal_num:     int
    trick_num:    int

    # other instance vars, for context (and whatever)
    match:        'Match'
    game:         'Game'
    _deal:        'Deal'  # this is the real deal (haha)
    trick:        Trick
    discarded:    Card    # discard returned from remote
    last_bid:     int     # positon of last bid synced with remote
    sync_swap:    bool    # whether swap was synced with remote
    last_play:    int     # sequence of last play synced with remote
    lead_pos:     int     # for current trick

    def __init__(self, **kwargs):
        """See base class.
        """
        super().__init__(**kwargs)
        # we consider the `requests` stuff to be part of the framework here (the word
        # "session" used elsewhere in this module refers to the session component of the
        # EuchreEndpoint interface)
        req_session = Session()
        req_session.headers.update(self.http_headers)
        self.req_session = req_session

        self.token      = None
        self.card_map   = None
        self.suit_map   = None
        self.card_rvmap = None
        self.suit_rvmap = None
        self.game_num   = -1
        self.deal_num   = -1
        self.trick_num  = -1
        self.match      = None
        self.game       = None
        self._deal      = None
        self.trick      = None
        self.discarded  = None
        self.last_bid   = None
        self.sync_swap  = None
        self.last_play  = None
        self.lead_pos   = None

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class.
        """
        if def_bid:
            assert not deal.is_partner_caller
            # remote engine currently doesn't support defending alone, so we just forgo
            # the `DEFENSE` endpoint completely
            return Bid(defend_suit, False)

        assert isinstance(self.last_bid, int)
        self.catchup_bids(deal)
        self.last_bid += 1
        return self.request_bid(deal)

    def discard(self, deal: DealState) -> Card:
        """See base class.
        """
        assert self.sync_swap is False
        self.sync_swap = True
        return self.request_swap(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class.
        """
        if not self.trick:
            self.new_trick(deal, trick)
        assert isinstance(self.last_play, int)
        self.catchup_plays(deal, trick)
        self.last_play += 1
        return self.request_play(deal, trick, valid_plays)

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """See base class.

        Note that this strategy may represent both players on a team, so we need to make
        sure that we are handling each logical notification only once.
        """
        match notice_type:
            case StrategyNotice.CARDS_DEALT:
                if not self.match:
                    self.new_match()
                if not self.game:
                    self.new_game()
                if not self._deal:
                    self.new_deal(deal)
            case StrategyNotice.BIDDING_OVER:
                # TODO: we shouldn't call these catchup calls twice!!!
                self.catchup_bids(deal)
                self.catchup_swap(deal)
                # NOTE: `new_trick()` can't be called here, since the trick hasn't been
                # added to the deal yet (so this has to be done in `play_card()`)
            case StrategyNotice.TRICK_COMPLETE:
                if self.trick:
                    self.catchup_plays(deal, self.trick)
                    self.trick_complete(deal)
            case StrategyNotice.DEAL_COMPLETE:
                if self._deal:
                    self.deal_complete(deal)
                # TEMP (until we add notifications for game and match)!!!
                #self.notify(deal, StrategyNotice.GAME_COMPLETE)
                #self.notify(deal, StrategyNotice.MATCH_COMPLETE)
                # /TEMP
            case StrategyNotice.GAME_COMPLETE:
                if self.game:
                    self.game_complete()
            case StrategyNotice.MATCH_COMPLETE:
                if self.match:
                    self.match_complete()

    def get_token(self) -> str:
        """Return unique session token tied to this ``Strategy`` instance (currently
        computed as hex digit representation of `id(self)`).
        """
        return hex(id(self))[2:]

    def request(self, req: EpReq, path: EpPath, status: EpStatusT, addl_args: dict,
                validate_args: list[str]) -> dict:
        """Wrapper for requests to server; a few comments on method arguments:

        - ``status`` - if specified as a single value, it will be passed into the request
          and validated in the response; if specified as a tuple, the two values will be
          individually used in the request and validated in the response, respectively
        - ``addl_args`` - in addition to ``token`` and ``status``
        - ``validate_args`` - list of args to validate on output; if ``None``, then all
          ``addl_args`` entries are validated

        Note that "validating" args means ensuring that the value in the response matches
        that in the request (as specified by the API).
        """
        addl_args = addl_args or {}
        if addl_args and validate_args is None:
            validate_args = list(addl_args.keys())
        else:
            validate_args = validate_args or []
        if status and type(status) is EpStatus:
            status = (status, status)

        url = self.server_url + path
        data = {'token': self.token}
        validate_args.append('token')
        if addl_args:
            data.update(addl_args)
        if status:
            data['status'] = status[0]

        try:
            log.debug(f"Request: {req} {path} {data}")
            if req is EpReq.GET:
                r = self.req_session.request(req, url, params=data)
            else:
                r = self.req_session.request(req, url, json=data)
            r.raise_for_status()
        except HTTPError as e:
            raise SystemExit(e)

        result = r.json()
        log.debug(f"Response: {result}")
        # TEMP: brittle integrity checks for now!!!
        for arg in validate_args:
            assert arg in data
            assert arg in result
            assert result[arg] == data[arg]
        if status:
            assert result['status'] == status[1]

        return result

    def map_deck(self, deck: Deck, dir: Dir = Dir.FROM) -> list[int]:
        """Return remapped deck in the specified "direction of travel".  We actually only
        need to do this in the outbound (i.e. ``FROM``) direction.  In contrast to
        ``map_card()`` and ``map_suit()``, we take an actual `Deck` instance as input,
        though the output uses card indexes rather than objects.

        The output format is (for card positions 0-23):

        - 0-4:   hand 0
        - 5-9:   hand 1
        - 10-14: hand 2
        - 15-29: hand 3
        - 20:    turn card
        - 21-23: buries

        The rationale is that this is more universal/canonical.  If the actual remote
        engine uses a different representation, that remapping should be done in the
        connector.
        """
        assert dir is Dir.FROM
        remapped = deck[0:20:4] + deck[1:20:4] + deck[2:20:4] + deck[3:20:4] + deck[20:]
        assert len(remapped) == len(deck)
        return [card.idx for card in remapped]

    def map_card(self, card: int, dir: Dir = Dir.FROM) -> int:
        """Return remapped card in the specified "direction of travel"; note that we use
        the card index (position within ``card.CARDS``) as the representation to keep
        things simple.
        """
        return self.card_map[card] if dir is Dir.FROM else self.card_rvmap[card]

    def map_suit(self, suit: int, dir: Dir = Dir.FROM) -> int:
        """Return remapped suit in the specified "direction of travel"; note that we use
        the suit index (position within ``card.SUITS``) as the representation to keep
        things simple.
        """
        if suit < 0:
            return suit
        return self.suit_map[suit] if dir is Dir.FROM else self.suit_rvmap[suit]

    def new_match(self) -> None:
        """Start new match on remote server.  Note that we are currently creating a new
        request session for each match.
        """
        self.token = self.get_token()
        result = self.request(EpReq.POST, EpPath.SESSION, EpActivate, None, None)
        self.match = object()  # TEMP: dummy match!!!

        self.card_map = result['cards']
        self.suit_map = result['suits']

        self.card_rvmap = [None] * len(self.card_map)
        for i, card_idx in enumerate(self.card_map):
            self.card_rvmap[card_idx] = i

        self.suit_rvmap = [None] * len(self.suit_map)
        for i, suit_idx in enumerate(self.suit_map):
            self.suit_rvmap[suit_idx] = i
        # HACK in a special reverse mapping to cover "no suit" (LATER, should be handled
        # in the remote endpoint code!)
        self.suit_rvmap.append(-1)

    def match_complete(self) -> None:
        """Notify remote server that match is complete.  Also tear down the remote session
        (since we are correlating them to the match).
        """
        result = self.request(EpReq.PATCH, EpPath.SESSION, EpStatus.COMPLETE, None, None)

        # reset and/or assert relative counters
        assert self.trick_num == -1
        assert self.deal_num == -1
        assert self.trick is None
        assert self._deal is None
        self.game = None
        self.game_num = -1
        self.match = None
        self.token = None

    def new_game(self) -> None:
        """Start new game on remote server.
        """
        self.game_num += 1
        self.game = object()  # TEMP: dummy game!!!

        addl_args = {
            'gameNum': self.game_num
        }
        result = self.request(EpReq.POST, EpPath.GAME, EpActivate, addl_args, None)

    def game_complete(self) -> None:
        """Notify remote server that game is complete.
        """
        addl_args = {
            'gameNum': self.game_num
        }
        result = self.request(EpReq.PATCH, EpPath.GAME, EpStatus.COMPLETE, addl_args, None)

        # reset and/or assert relative counters
        assert self.trick_num == -1
        assert self._deal is None
        self.deal_num = -1

    def new_deal(self, deal: DealState) -> None:
        """Start new deal on remote server.
        """
        assert self._deal is None
        self._deal = deal.player_state['_deal']
        self.deal_num += 1
        self.discarded = None
        self.last_bid = -1
        self.sync_swap = False
        self.lead_pos = 0

        # convert card representation to canonical form
        cards = [self.map_card(x) for x in self.map_deck(self._deal.deck)]
        addl_args = {
            'gameNum': self.game_num,
            'dealNum': self.deal_num,
            'cards':   cards
        }
        validate = [x for x in addl_args.keys() if x != 'cards']
        result = self.request(EpReq.POST, EpPath.DEAL, EpActivate, addl_args, validate)

    def deal_complete(self, deal: DealState) -> None:
        """Notify remote server that deal is complete.
        """
        addl_args = {
            'gameNum': self.game_num,
            'dealNum': self.deal_num
        }
        result = self.request(EpReq.PATCH, EpPath.DEAL, EpStatus.COMPLETE, addl_args, None)

        # reset and/or assert relative counters
        self._deal = None
        self.trick_num = -1
        self.discarded = None
        self.last_bid = None
        self.sync_swap = None
        self.last_play = None
        self.lead_pos = None

    def new_trick(self, deal: DealState, trick: Trick) -> None:
        """Start new trick on remote server.
        """
        assert self.trick is None
        self.trick = trick
        self.trick_num += 1
        self.last_play = -1

        addl_args = {
            'gameNum':  self.game_num,
            'dealNum':  self.deal_num,
            'trickNum': self.trick_num,
            'leadPos':  self.lead_pos
        }
        validate = [x for x in addl_args.keys() if x != 'leadPos']
        result = self.request(EpReq.POST, EpPath.TRICK, EpActivate, addl_args, validate)

    def trick_complete(self, deal: DealState) -> None:
        """Notify remote server that trick is complete.
        """
        addl_args = {
            'gameNum': self.game_num,
            'dealNum': self.deal_num,
            'trickNum': self.trick_num
        }
        result = self.request(EpReq.PATCH, EpPath.TRICK, EpStatus.COMPLETE, addl_args, None)

        # reset and/or assert relative counters
        self.lead_pos = self.trick.winning_pos
        self.trick = None

    def request_bid(self, deal: DealState) -> Bid:
        """Request bid from remote server.
        """
        addl_args = {
            'gameNum':  self.game_num,
            'dealNum':  self.deal_num,
            'round':    deal.bid_round,
            'turnCard': self.map_card(deal.turn_card.idx),
            'pos':      deal.pos
        }
        result = self.request(EpReq.GET, EpPath.BID, None, addl_args, None)
        suit_idx = self.map_suit(result['suit'], Dir.TO)
        if suit_idx < 0:
            return PASS_BID
        return Bid(SUITS[suit_idx], result['alone'])

    def notify_bid(self, deal: DealState, bid_pos: int, bid: Bid) -> None:
        """Notify remote server of a bid.
        """
        # `null_suit` is not used/understood by the remote interface, and `defend_suit` is
        # not yet implemented, so we skip both for now!
        if bid.suit in (null_suit, defend_suit):
            return

        addl_args = {
            'gameNum':  self.game_num,
            'dealNum':  self.deal_num,
            'round':    deal.bid_round,
            'turnCard': self.map_card(deal.turn_card.idx),
            'pos':      bid_pos,
            'suit':     self.map_suit(bid.suit.idx),
            'alone':    bid.alone
        }
        validate = [x for x in addl_args.keys() if x not in ('suit', 'alone')]
        result = self.request(EpReq.POST, EpPath.BID, None, addl_args, validate)

    def request_swap(self, deal: DealState) -> Card:
        """Request swap (discard) from remote server.
        """
        assert self.discarded is None
        addl_args = {
            'gameNum':        self.game_num,
            'dealNum':        self.deal_num,
            'declarerPos':    deal.caller_pos,
            'turnCard':       self.map_card(deal.turn_card.idx),
            'pos':            deal.pos,
            'swappableCards': [self.map_card(card.idx) for card in deal.hand]
        }
        validate = [x for x in addl_args.keys() if x != 'swappableCards']
        result = self.request(EpReq.GET, EpPath.SWAP, None, addl_args, validate)
        self.discarded = CARDS[self.map_card(result['card'], Dir.TO)]
        return self.discarded

    def notify_swap(self, deal: DealState, swap_pos: int, card: Card) -> None:
        """Notify remote server of a swap.
        """
        addl_args = {
            'gameNum':     self.game_num,
            'dealNum':     self.deal_num,
            'declarerPos': deal.caller_pos,
            'turnCard':    self.map_card(deal.turn_card.idx),
            'pos':         swap_pos,
            'card':        self.map_card(card.idx)
        }
        validate = [x for x in addl_args.keys() if x != 'card']
        result = self.request(EpReq.POST, EpPath.SWAP, None, addl_args, validate)

    def request_play(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """Request swap from remote server.
        """
        addl_args = {
            'gameNum':       self.game_num,
            'dealNum':       self.deal_num,
            'trickNum':      self.trick_num,
            'trickSeq':      (deal.pos - self.lead_pos) % 4,
            'pos':           deal.pos,
            'playableCards': [self.map_card(card.idx) for card in valid_plays]
        }
        validate = [x for x in addl_args.keys() if x != 'playableCards']
        result = self.request(EpReq.GET, EpPath.PLAY, None, addl_args, validate)
        card = CARDS[self.map_card(result['card'], Dir.TO)]
        return card

    def notify_play(self, deal: DealState, trick: Trick, play_pos: int, card: Card) -> None:
        """Notify remote server of a card play.
        """
        # REVISIT: for now, don't send non-play notifications (since the server side is
        # handling skipped bids), but we may want to add this back to keep state synced
        # more explicitly!!!
        if card is None:
            return
        addl_args = {
            'gameNum':  self.game_num,
            'dealNum':  self.deal_num,
            'trickNum': self.trick_num,
            'trickSeq': (play_pos - self.lead_pos) % 4,
            'pos':      play_pos,
            'card':     self.map_card(card.idx)
        }
        validate = [x for x in addl_args.keys() if x != 'card']
        result = self.request(EpReq.POST, EpPath.PLAY, None, addl_args, validate)

    def catchup_bids(self, deal: DealState) -> None:
        """Catchup on bid notifications.
        """
        while self.last_bid < len(deal.bids) - 1:
            self.last_bid += 1
            self.notify_bid(deal, self.last_bid, deal.bids[self.last_bid])

    def catchup_swap(self, deal: DealState) -> None:
        """Catchup on swap notification.
        """
        if self.sync_swap:
            return

        if self.discarded:
            assert self.discarded is self._deal.discard
        elif self._deal.discard:
            self.sync_swap = True
            self.notify_swap(deal, DEALER_POS, self._deal.discard)

    def catchup_plays(self, deal: DealState, trick: Trick) -> None:
        """Catchup on play notifications.
        """
        while self.last_play < len(trick.plays) - 1:
            self.last_play += 1
            self.notify_play(deal, trick, *trick.plays[self.last_play])
