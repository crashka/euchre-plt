# -*- coding: utf-8 -*-

from enum import Enum, StrEnum

from requests import Session, HTTPError

from ..card import Card, Deck
from ..euchre import Bid, PASS_BID, Trick, DealState
from .base import Strategy, StrategyNotice

#########
# Enums #
#########

# direction of "travel" relative to us (e.g. for card mapping)
Dir = Enum('Dir', 'TO FROM')

class EpReq(StrEnum):
    """Note: the value for each member must correpond to a valid request type
    the the `requests` module
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
    """Invocation of remote strategies through the `EuchreEndpoint`_ interface

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

    # other instance vars
    _deal:        'Deal'  # this is the real deal (haha)

    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)
        # we consider the `requests` stuff to be part of the framework here (the word
        # "session" in method names refers to the session for the EuchreEndpoint
        # interface)
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
        self._deal      = None

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class
        """
        return PASS_BID

    def discard(self, deal: DealState) -> Card:
        """See base class
        """
        return deal.hand.cards[0]

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class
        """
        return valid_plays[0]

    def notify(self, deal: DealState, notice_type: StrategyNotice) -> None:
        """See base class
        """
        match notice_type:
            case StrategyNotice.CARDS_DEALT:
                self._deal = deal.player_state['_deal']
                if not self.token:
                    self.new_session()
                    self.new_game()
                    self.new_deal()
            case StrategyNotice.BIDDING_OVER:
                self.new_trick()
            case StrategyNotice.TRICK_COMPLETE:
                self.trick_complete()
            case StrategyNotice.DEAL_COMPLETE:
                self.deal_complete()
                self.game_complete()
                self.session_complete()

    def get_token(self) -> str:
        """Return unique session token tied to this ``Strategy`` instance (currently
        computed as hex digit representation of `id(self)`)
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
        that in the request (as specified by the API)
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
            r = self.req_session.request(req, url, json=data)
            r.raise_for_status()
        except HTTPError as e:
            raise SystemExit(e)

        result = r.json()
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
        need to do this in the outbound (`FROM`) direction.  In contrast to `map_card()`
        and `map_suit()`, we take an actual `Deck` instance as input, though the output
        uses card indexes rather than objects.

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
        things simple
        """
        return self.card_map[card] if dir is Dir.FROM else self.card_rvmap[card]

    def map_suit(self, suit: int, dir: Dir = Dir.FROM) -> int:
        """Return remapped suit in the specified "direction of travel"; note that we use
        the suit index (position within ``card.SUITS``) as the representation to keep
        things simple
        """
        return self.suit_map[suit] if dir is Dir.FROM else self.suit_rvmap[suit]

    def new_session(self) -> None:
        """Start new session on remote server
        """
        self.token = self.get_token()
        result = self.request(EpReq.POST, EpPath.SESSION, EpActivate, None, None)

        self.card_map = result['cards']
        self.suit_map = result['suits']

        self.card_rvmap = [None] * len(self.card_map)
        for i, card_idx in enumerate(self.card_map):
            self.card_rvmap[card_idx] = i

        self.suit_rvmap = [None] * len(self.suit_map)
        for i, suit_idx in enumerate(self.suit_map):
            self.suit_rvmap[suit_idx] = i

    def session_complete(self) -> None:
        """Notify remote server that session is complete
        """
        result = self.request(EpReq.PATCH, EpPath.SESSION, EpStatus.COMPLETE, None, None)

        # reset and/or assert relative counters
        assert self.trick_num == -1
        assert self.deal_num == -1
        self.game_num = -1
        self.token = None

    def new_game(self) -> None:
        """Start new game on remote server
        """
        self.game_num += 1

        addl_args = {'gameNum': self.game_num}
        result = self.request(EpReq.POST, EpPath.GAME, EpActivate, addl_args, None)

    def game_complete(self) -> None:
        """Notify remote server that game is complete
        """
        addl_args = {'gameNum': self.game_num}
        result = self.request(EpReq.PATCH, EpPath.GAME, EpStatus.COMPLETE, addl_args, None)

        # reset and/or assert relative counters
        assert self.trick_num == -1
        self.deal_num = -1

    def new_deal(self) -> None:
        """Start new deal on remote server
        """
        self.deal_num += 1

        # we just pass the deck in the order we utilize; it is up to the remote side to
        # consume the order of the cards appropriately
        cards = [self.map_card(x) for x in self.map_deck(self._deal.deck)]
        addl_args = {'gameNum': self.game_num, 'dealNum': self.deal_num, 'cards': cards}
        validate = [x for x in addl_args.keys() if x != 'cards']
        result = self.request(EpReq.POST, EpPath.DEAL, EpActivate, addl_args, validate)

    def deal_complete(self) -> None:
        """Notify remote server that deal is complete
        """
        addl_args = {'gameNum': self.game_num, 'dealNum': self.deal_num}
        result = self.request(EpReq.PATCH, EpPath.DEAL, EpStatus.COMPLETE, addl_args, None)

        # reset and/or assert relative counters
        self.trick_num = -1

    def new_trick(self) -> None:
        """Notify remote server that trick is complete
        """
        pass

    def trick_complete(self) -> None:
        """Notify remote server that trick is complete
        """
        pass
