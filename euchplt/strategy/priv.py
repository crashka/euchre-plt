# -*- coding: utf-8 -*-

"""Shhh, not saying whether "priv" stands for "priviledged" or "private" (at least not in
the docstring...)
"""

from .base import Strategy

# Super-secret tuple of privileged subclasses (access to full deal information)
_PRIVILEDGED = ('StrategyRemote',)

def _priv(cls) -> bool:
    """Shhh...
    """
    return cls.__name__ in _PRIVILEDGED

setattr(Strategy, '_priv', classmethod(_priv))
