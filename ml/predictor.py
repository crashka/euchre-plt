# -*- coding: utf-8 -*-

from enum import StrEnum
from numbers import Number
import os.path
import time

import pandas as pd
from autogluon.tabular import TabularDataset, TabularPredictor

from euchplt.core import cfg, BASE_DIR, log

#################################
# TEMP (move to `ml` module)!!! #
#################################

cfg.load('ml_models.yml')
ml_models = cfg.config('ml_models')

ML_DIR     = os.path.join(BASE_DIR, 'ml')
MODEL_REPO = os.path.join(ML_DIR, 'models')

class ProblemType(StrEnum):
    REGRESSION = "regression"
    QUANTILE   = "quantile"
    MULTICLASS = "multiclass"

class Predictor:
    """Wrapper around ML model--currently hardwired to Autogluon implementation, but later
    we can subclass (after validating abstract design).
    """
    name:      str
    model:     dict
    ag_pred:   TabularPredictor
    quant_idx: int | None = None

    def __init__(self, name: str, **kwargs):
        self.name = name
        self.model = ml_models.get(self.name)
        if not self.model:
            raise RuntimeError(f"ML Model '{self.name}' is not known")
        # TODO: integrity checks on model definition (problem type, label, etc.)!!!
        t1 = time.perf_counter()
        self.ag_pred = TabularPredictor.load(self.model_path())
        t2 = time.perf_counter()
        self.ag_pred.persist()
        t3 = time.perf_counter()
        log.debug(f"Model \"{self.name}\" load time: {t2-t1:.2f} secs")
        log.debug(f"Model \"{self.name}\" persist time: {t3-t2:.2f} secs")

        if self.problem_type == ProblemType.QUANTILE:
            level = kwargs.get('quantile_level')
            if level not in self.model['quantile_levels']:
                raise RuntimeError(f"Bad quantile level {level} for model '{self.name}'")
            self.quant_idx = self.model['quantile_levels'].index(level)

    @property
    def problem_type(self) -> str:
        """Return problem type for the model.
        """
        return self.ag_pred.problem_type

    @property
    def label(self) -> str:
        """Return label column for the model.
        """
        return self.ag_pred.label

    def model_path(self) -> str:
        """Get name of directory containing the model to be loaded.
        """
        return os.path.join(MODEL_REPO, self.model['model_dir'])

    def get_values(self, features: list[dict]) -> list[Number]:
        """Return model outputs corresponding to list of dicts (or NamedTuples) containing
        input features.  The means of extracting and/or casting the values from the model
        output depends on the problem type.
        """
        feat_df = pd.DataFrame(features)
        t1 = time.perf_counter()
        pred = self.ag_pred.predict(feat_df, as_pandas=False)
        t2 = time.perf_counter()
        nvalues = len(features.index)
        nvalues_str = f"({nvalues} value{'s' if nvalues > 1 else ''})"
        log.debug(f"Model \"{self.name}\" predict time {nvalues_str}: {t2-t1:.3f} secs")
        if self.quant_idx is not None:
            return pred[:, self.quant_idx].astype(float)
        elif self.problem_type == ProblemType.MULTICLASS:
            return pred.astype(int)
        else:
            return pred.astype(float)
