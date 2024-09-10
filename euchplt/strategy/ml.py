# -*- coding: utf-8 -*-

import os.path

import pandas as pd

from ..card import SUITS, Card
from ..euchre import Bid, defend_suit, DEFEND_ALONE, PASS_BID, Trick, DealState
from .base import Strategy
from ml.strategy import BidDataAnalysis, PlayDataAnalysis
from ml.predictor import Predictor

##############
# StrategyML #
##############

DUMMY_RUN_ID = 'dummy'
DUMMY_KEY    = []

class StrategyML(Strategy):
    """Implement a bidding and/or playing strategy based on machine learning models
    trained usng the top-level ``ml`` module.  For now, we are only supporting a single ML
    model-development framework (Autogluon), so we will just hardwire ``StrategyML`` to
    that format, but later we will need to further subclass.

    Note that the current ML models do not explicitly consider discard options (leaving
    that up to the non-modeled phase of the game), so we will generally try and emulate
    those conditions by using the discard strategy invoked for the training process.
    """
    # config parameters
    bid_model:        str
    bid_pred_params:  dict
    call_thresh:      float
    alone_thresh:     float
    def_thresh:       float
    bid_aggression:   int
    discard_strategy: str
    play_model:       str
    play_pred_params: dict
    hand_analysis:    dict
    play_analysis:    dict
    # instance variables
    bid_pred:         Predictor
    play_pred:        Predictor
    discard_inst:     Strategy

    def __init__(self, **kwargs):
        """See base class.
        """
        super().__init__(**kwargs)
        if self.bid_model:
            self.bid_pred = Predictor(self.bid_model, **self.bid_pred_params)
        else:
            self.bid_pred = None
        if self.play_model:
            self.play_pred = Predictor(self.play_model, **self.play_pred_params)
        else:
            self.play_pred = None
        if self.discard_strategy:
            self.discard_inst = Strategy.new(self.discard_strategy)
        else:
            self.discard_inst = None

    def bid(self, deal: DealState, def_bid: bool = False) -> Bid:
        """See base class.

        If the 0x01 flag for ``bid_aggression`` is *not* set, then always call to play
        with partner if possible (even if ``alone_tresh`` is exceeded), otherwise choose
        the alone option with the higher margin over threshold.
        """
        if not self.bid_pred:
            raise RuntimeError("Model not configured for bidding")

        analysis = BidDataAnalysis(deal, **self.hand_analysis)
        if def_bid:
            def_feat = analysis.get_features(DEFEND_ALONE, as_dict=True)
            feat_df  = pd.DataFrame([def_feat])
            values   = self.bid_pred.get_values(feat_df)
            alone    = values[0] > self.alone_thresh
            return Bid(defend_suit, alone)

        if deal.bid_round == 1:
            call_bid     = Bid(deal.turn_card.suit, False)
            alone_bid    = Bid(deal.turn_card.suit, True)
            call_feat    = analysis.get_features(call_bid, as_dict=True)
            alone_feat   = analysis.get_features(alone_bid, as_dict=True)
            feat_df      = pd.DataFrame([call_feat, alone_feat])
            values       = self.bid_pred.get_values(feat_df)
            call_margin  = values[0] - self.call_thresh
            alone_margin = values[1] - self.alone_thresh

            if call_margin <= 0.0:
                if alone_margin <= 0.0:
                    return PASS_BID
                else:
                    return alone_bid
            elif alone_margin <= 0.0:
                return call_bid

            assert call_margin > 0 and alone_margin > 0
            if not (self.bid_aggression ^ 0x01):
                return call_bid
            return alone_bid if alone_margin > call_margin else call_bid
        else:
            assert deal.bid_round == 2
            call_bids   = []
            alone_bids  = []
            call_feats  = []
            alone_feats = []
            for suit in SUITS:
                if suit == deal.turn_card.suit:
                    continue
                call_bid = Bid(suit, False)
                alone_bid = Bid(suit, True)
                call_bids.append(call_bid)
                alone_bids.append(alone_bid)
                call_feats.append(analysis.get_features(call_bid, as_dict=True))
                alone_feats.append(analysis.get_features(alone_bid, as_dict=True))
            call_feat_df = pd.DataFrame(call_feats)
            alone_feat_df = pd.DataFrame(alone_feats)
            call_values = self.bid_pred.get_values(call_feat_df)
            alone_values = self.bid_pred.get_values(alone_feat_df)

            # tuple: (bid, high_value, margin)
            best_call = (None, self.call_thresh, -1.0)
            best_alone = (None, self.alone_thresh, -1.0)
            for i, value in enumerate(call_values):
                if value > best_call[1]:
                    best_call = (call_bids[i], value, value - self.call_thresh)
            for i, value in enumerate(alone_values):
                if value > best_alone[1]:
                    best_alone = (alone_bids[i], value, value - self.alone_thresh)
            if best_call[0] is None:
                if best_alone[0] is None:
                    return PASS_BID
                else:
                    return best_alone[0]
            elif best_alone[0] is None:
                return best_call[0]

            assert isinstance(best_call[0], Bid) and isinstance(best_alone[0], Bid)
            if not (self.bid_aggression ^ 0x01):
                return best_call[0]
            return best_alone[0] if best_alone[2] > best_call[2] else best_call[0]

        assert False, "NOTREACHED"

    def discard(self, deal: DealState) -> Card:
        """See base class.
        """
        return self.discard_inst.discard(deal)

    def play_card(self, deal: DealState, trick: Trick, valid_plays: list[Card]) -> Card:
        """See base class.
        """
        if not self.play_pred:
            raise RuntimeError("Model not configured for playing")

        if len(valid_plays) == 1:
            return valid_plays[0]

        bid_analysis = BidDataAnalysis(deal, **self.hand_analysis)
        bid_features = bid_analysis.get_features(deal.contract, as_dict=True)
        analysis = PlayDataAnalysis(deal, **self.play_analysis,
                                    run_id=DUMMY_RUN_ID,
                                    valid_plays=valid_plays,
                                    bid_features=bid_features)
        feats = []
        for card in valid_plays:
            feats.append(analysis.get_features(card, DUMMY_KEY, as_dict=True))
        feat_df = pd.DataFrame(feats)
        values = self.play_pred.get_values(feat_df)
        # tuple: (card, high_value)
        best = (None, -10.0)
        for i, value in enumerate(values):
            if value > best[1]:
                best = (valid_plays[i], value)
        return best[0]
