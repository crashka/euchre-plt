# -*- coding: utf-8 -*-

from enum import Enum

from requests import Session, HTTPError

from ..card import Card
from ..euchre import Bid, PASS_BID, Trick, DealState
from .base import Strategy

##################
# StrategyRemote #
##################

class EpReq(Enum):
    """Note: the value for each member must correpond to a valid request type
    the the `requests` module
    """
    GET      = "get"
    POST     = "post"
    PATCH    = "patch"

class EpPath(Enum):
    SESSION  = "/session"
    GAME     = "/game"
    DEAL     = "/deal"
    TRICK    = "/trick"

class EpStatus(Enum):
    NEW      = "new"
    ACTIVE   = "active"
    UPDATE   = "update"
    COMPLETE = "complete"

# a couple of helpful aliases
EpActivate = (EpStatus.NEW, EpStatus.ACTIVE)
EpStatusT = EpStatus | tuple[EpStatus, EpStatus]

class StrategyRemote(Strategy):
    """Invocation of remote strategies through the `EuchreEndpoint`_ interface

    .. _EuchreEndpoint: https://github.com/crashka/EuchreEndpoint
    """
    server_url:   str
    http_headers: dict[str, str]

    # `requests` stuff
    session:      Session

    # `EuchreEndpoint` stuff
    token:        str
    card_map:     list[int]
    suit_map:     list[int]
    game_num:     int
    deal_num:     int
    trick_num:    int

    def __init__(self, **kwargs):
        """See base class
        """
        super().__init__(**kwargs)
        self.token     = self.get_token()
        self.card_map  = None
        self.card_map  = None
        self.game_num  = -1
        self.deal_num  = -1
        self.trick_num = -1

        # we consider the `requests` stuff to be part of the framework here
        # (the word "session" in method names refers to the session for the
        # EuchreEndpoint interface)
        session = Session()
        session.headers.update(self.http_headers)
        self.session = session

        # TEMP: end-to-end testing of call sequence!!!
        self.new_session()
        self.new_game()
        self.new_deal()
        self.new_trick()

        self.trick_complete()
        self.deal_complete()
        self.game_complete()
        self.session_complete()

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

        url = self.server_url + path.value
        data = {'token': self.token}
        validate_args.append('token')
        if addl_args:
            data.update(addl_args)
        if status:
            data['status'] = status[0].value

        try:
            r = self.session.request(req.value, url, json=data)
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
            assert result['status'] == status[1].value

        return result

    def new_session(self) -> None:
        """Start new session on remote server
        """
        result = self.request(EpReq.POST, EpPath.SESSION, EpActivate, None, None)

        self.card_map = result['cards']
        self.suit_map = result['suits']

    def session_complete(self) -> None:
        """Notify remote server that session is complete
        """
        result = self.request(EpReq.PATCH, EpPath.SESSION, EpStatus.COMPLETE, None, None)

        # reset and/or assert relative counters
        assert self.trick_num == -1
        assert self.deal_num == -1
        self.game_num = -1

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

        cards = self.card_map  # TEMP: dummy value for now!!!
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
