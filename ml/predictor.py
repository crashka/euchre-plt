# -*- coding: utf-8 -*-

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

class Predictor:
    """Wrapper around ML model--currently hardwired to Autogluon implementation, but later
    we can subclass (after validating abstract design).
    """
    name:    str
    model:   dict
    ag_pred: TabularPredictor

    def __init__(self, name: str):
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

    @property
    def label(self) -> str:
        """Return label column for the model.
        """
        return self.ag_pred.label

    def model_path(self) -> str:
        """Get name of directory containing the model to be loaded.
        """
        return os.path.join(MODEL_REPO, self.model['model_dir'])

    def get_values(self, features_in: pd.DataFrame) -> list[float]:
        """Given one or more tuples of intput features (encapsulated as a DataFrame),
        return corresponding model outputs.

        TODO: for now, we are assuming ``float`` values as model output, but later, this
        will vary by problem type!!!
        """
        t1 = time.perf_counter()
        pred = self.ag_pred.predict(features_in, as_pandas=False)
        t2 = time.perf_counter()
        nvalues = len(features_in.index)
        nvalues_str = f"({nvalues} value{'s' if nvalues > 1 else ''})"
        log.debug(f"Model \"{self.name}\" predict time {nvalues_str}: {t2-t1:.3f} secs")
        return [float(x) for x in pred]
