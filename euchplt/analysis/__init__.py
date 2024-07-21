# -*- coding: utf-8 -*-

"""This module provides helper classes for the ``strategy`` module.  The primary base
classes are ``Hand Analysis`` and ``PlayAnalysis``, both of which can be subclassed by any
strategy that requires additional or specialized functionality.
"""

from .base import SuitCtx, SUIT_CTX, HandAnalysis, PlayAnalysis
from .smart import HandAnalysisSmart
