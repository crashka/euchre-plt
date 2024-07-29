#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Module (and command line tool) for generating nice looking YAML from a data structure
(dict or list).  More flexible than ``yaml.dumps()`` in the ``pyyaml`` package.
"""

import sys
from numbers import Number
from typing import NamedTuple
from collections.abc import Mapping, Sequence
import fileinput

from euchplt.utils import parse_argv

##################
# module library #
##################

Scalar    = Number | str | None
# note: not using `Sequence` here, since it includes str` (and `MutableSequence`
# is not really right!)
Nonscalar = Mapping | list
AnyT      = Scalar | Nonscalar

DFLT_INDENT  = 2
DFLT_OFFSET  = 0
DFLT_MAXSIZE = 10
DFLT_MAXLINE = 90
DFLT_PADDING = 2

# a couple of utility functions
def all_scalars(data: Sequence) -> bool:
    """Return true if all elements of the Sequence are scalars

    Note: the logic actually counts nonscalars
    """
    nonscalars = [x for x in data if isinstance(x, Nonscalar)]
    return len(nonscalars) == 0

def max_keylen(data: Mapping) -> int:
    """Return the maximum key length for the Mapping
    """
    keylens = [len(x) for x in data.keys()]
    return max(keylens)

class YamlGenerator:
    """Generate nice looking YAML

    Usage::

      from to_yaml import to_yaml

      data_yaml = to_yaml(data, indent=2, offset=4)

    Supports the following keyword args:

    - ``indent`` - level of indentation between levels (default = 2)
    - ``offset`` - offset for the entire output, e.g. representing the interior of a
      document body (default = 0)
    - ``maxsize`` - max number of items for single- vs. multi-line representations of
      lists of dicts (default = 10)
    - ``maxline`` - max line length for single- vs. multi-line representations of lists or
      dicts (default = 90)
    - ``padding`` - minimum padding between key name + colon and corresponding value for
      "associative arrays" (i.e. dicts, in python) (default = 2)

    Note that supported types in the input data include: ``list``, ``dict``, and scalars
    (``str``, ``Number``, ``bool``, ``NoneType``, or anything else where ``repr()`` will
    yield a valid YAML representation)
    """
    indent:  int
    offset:  int
    maxsize: int
    maxline: int
    padding: int

    def __init__(self, **kwargs):
        self.indent  = kwargs.get('indent') or DFLT_INDENT
        self.offset  = kwargs.get('offset') or DFLT_OFFSET
        self.maxsize = kwargs.get('maxsize') or DFLT_MAXSIZE
        self.maxline = kwargs.get('maxline') or DFLT_MAXLINE
        self.padding = kwargs.get('padding') or DFLT_PADDING

    def single_line(self, data: AnyT, pfx: str) -> str | None:
        """Format data for single-line output given the prefix for the line (used for
        determining the overall line length as well as generating the string); return
        ``None`` if data does not qualify (e.g. ``maxsize`` or ``maxline`` exceeded)

        Note that scalar data always comes back as a single line
        """
        if isinstance(data, Scalar):
            return pfx + ' ' + repr(data)

        vals = data.values() if isinstance(data, Mapping) else data
        if not all_scalars(vals):
            return None

        if len(data) > self.maxsize:
            return None

        line = pfx + ' ' + repr(data)
        if len(line) > self.maxline:
            return None

        return line

    def dict_data(self, data: dict, level: int) -> list[str]:
        """Return list of lines representing dict data as YAML
        """
        assert isinstance(data, dict)
        tabstop = ' ' * (level * self.indent)

        if len(data) == 0:
            return tabstop + '{}'

        output = []

        field_size = max_keylen(data) + self.padding
        for key, val in data.items():
            pfx = f"{tabstop}{key + ':':{field_size}}"
            if isinstance(val, dict):
                if line := self.single_line(val, pfx):
                    output.append(line)
                else:
                    output.append(pfx)
                    lines = self.dict_data(val, level + 1)
                    output.extend(lines)
            elif isinstance(val, list):
                if line := self.single_line(val, pfx):
                    output.append(line)
                else:
                    output.append(pfx)
                    lines = self.list_data(val, level + 1)
                    output.extend(lines)
            else:
                assert isinstance(val, Scalar)
                line = self.single_line(val, pfx)
                output.append(line)

        return output

    def list_data(self, data: list, level: int) -> list:
        """Return list of lines representing list data as YAML
        """
        assert isinstance(data, list)
        tabstop = ' ' * (level * self.indent)

        if len(data) == 0:
            return '[]'

        output = []
        pfx = tabstop + '-'
        for val in data:
            if isinstance(val, dict):
                if line := self.single_line(val, pfx):
                    output.append(line)
                else:
                    output.append(pfx)
                    lines = self.dict_data(val, level + 1)
                    output.extend(lines)
            elif isinstance(val, list):
                if line := self.single_line(val, pfx):
                    output.append(line)
                else:
                    output.append(pfx)
                    lines = self.list_data(val, level + 1)
                    output.extend(lines)
            else:
                assert isinstance(val, Scalar)
                line = self.single_line(val, pfx)
                output.append(line)

        return output

    def to_yaml(self, data: dict | list) -> str:
        """Return generated YAML
        """
        if isinstance(data, dict):
            lines = self.dict_data(data, level=0)
        elif isinstance(data, list):
            lines = self.dict_data(data, level=0)
        else:
            raise TypeError(f"Invalid input type ({type(data)})")

        tabstop = ' ' * self.offset
        return tabstop + ('\n' + tabstop).join(lines)

def to_yaml(data: dict | list, **kwargs) -> str:
    """Generate nice looking YAML, thin wrapper around ``YamlGenerator.to_yaml()``
    (hides the containing class)

    See ``YamlGenerator`` for supported keyword args and additional information
    """
    # delegate all validation, etc. to the class implementation
    generator = YamlGenerator(**kwargs)
    return generator.to_yaml(data)

#############
# test_data #
#############

test_data = {
    'new_strategy': {
        'hand_analysis': {
            'trump_values':     [0, 0, 0, 1, 2, 4, 7, 10],
            'suit_values':      [0, 0, 0, 2, 7, 10],
            'num_trump_scores': [0.0, 0.2, 0.3, 0.65, 0.9, 1.0],
            'off_aces_scores':  [0.0, 0.25, 0.6, 1.0],
            'voids_scores':     [0.0, 0.3, 0.7, 1.0],
            'scoring_coeff': {
                'trump_score':      20,
                'max_suit_score':   7,
                'num_trump_score':  27,
                'off_aces_score':   25,
                'voids_score':      21
            }
        },
        'turn_card_value':  [10, 15, 0, 20, 25, 30, 0, 50],
        'turn_card_coeff':  [25, 25, 25, 25],
        'bid_thresh':       [35, 35, 35, 35, 35, 35, 35, 35],
        'alone_margin':     [10, 10, 10, 10, 10, 10, 10, 10],
        'def_alone_thresh': [35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35],
        'test_1': [
            [10, 10, 10, 10, 10, 10, 10, 10],
            [35, 35, 35, 35, 35, 35, 35, 35]
        ],
        'test_2': [
            {
                'trump_score':      20,
                'max_suit_score':   7,
                'num_trump_score':  27,
                'off_aces_score':   25,
                'voids_score':      21
            },
            {
                'turn_card_value':  [10, 15, 0, 20, 25, 30, 0, 50],
                'turn_card_coeff':  [25, 25, 25, 25],
                'bid_thresh':       [35, 35, 35, 35, 35, 35, 35, 35],
                'alone_margin':     [10, 10, 10, 10, 10, 10, 10, 10],
                'def_alone_thresh': [35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35],
                'test1': [],
                'test2': {}
            },
            [],
            {}
        ]
    }
}

#####################
# command line tool #
#####################

def get_data(filename: str | None) -> str:
    """Get data from specified file (or stdin, if "-")

    Uses test data if filename is empty
    """
    if not filename:
        return test_data

    raise NotImplementedError("coming soon..")

def main() -> int:
    """Reformat a json or yaml file (or stream) as nice looking YAML

    Usage: to_yaml.py <filename> [<arg>=<value> ...]

      where: "-" for <filename> indicates stdin

    See ``YamlGenerator`` for supported keyword args and additional information
    """
    args, kwargs = parse_argv(sys.argv[1:])
    data = get_data(args)

    # for now, just working with test data, passing directive kwargs
    yaml = to_yaml(data, **kwargs)
    print(yaml)
    return 0

if __name__ == "__main__":
    sys.exit(main())
