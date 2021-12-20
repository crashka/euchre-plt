# -*- coding: utf-8 -*-

from collections.abc import Iterable, Sequence
from typing import Union, Optional
from numbers import Number
import os.path
import logging
import json
import re

import yaml

#####################
# Config Management #
#####################

DEFAULT_PROFILE = 'default'

class Config:
    """Manages YAML config information, features include:
      - Loading from multiple config files
      - Caching of aggregated config file parameters
      - Named "profiles" to override 'default' profile parameters

    Config file structure:
    ---
    default:
      my_section:
        my_param: value

    alt_profile:
      my_section:
        my_param: alt_value  # overwrites value from 'default' profile
    """
    config_dir:   Optional[str]
    filepaths:    list[str]        # list of file pathnames loaded
    profile_data: dict[str, dict]  # config indexed by profile (including 'default')

    def __init__(self, files: Union[str, Iterable[str]], config_dir: str = None):
        """Note that `files` can be specified as an iterable, or a comma-separated
        list of file names (no spaces)
        """
        if isinstance(files, str):
            load_files = files.split(',')
        else:
            if not isinstance(files, Iterable):
                raise RuntimeError("Bad argument, 'files' not iterable")
            load_files = list(files)

        self.config_dir = config_dir
        self.filepaths = []
        self.profile_data = {}
        for file in load_files:
            self.load(file)

    def load(self, file: str) -> bool:
        """Load a config file, overwriting existing parameter entries at the section
        level (i.e. direct children within a section).  Deeper merging within these
        top-level parameters is not supported.  Note that additional config files
        can be loaded at any time.  A config file that has already been loaded will
        be politely skipped, with a `False` return value being the only rebuke.
        """
        path = os.path.join(self.config_dir, file) if self.config_dir else os.path.realpath(file)
        if path in self.filepaths:
            return False

        with open(path, 'r') as f:
            cfg = yaml.safe_load(f)
            if not cfg:  # could be bad YAML or empty config
                raise RuntimeError(f"Could not load from '{file}'")

        for profile in cfg:
            if profile not in self.profile_data:
                self.profile_data[profile] = {}
            for section in cfg[profile]:
                if section not in self.profile_data[profile]:
                    self.profile_data[profile][section] = {}
                self.profile_data[profile][section].update(cfg[profile][section])

        self.filepaths.append(path)
        return True

    def config(self, section: str, profile: str = None) -> dict:
        """Get parameters for configuration section (empty dict is returned if
        section is not found).  If `profile` is specified, the parameter values
        for that profile override values from the 'default' profile (which must
        exist).
        """
        if DEFAULT_PROFILE not in self.profile_data:
            raise RuntimeError(f"Default profile ('{DEFAULT_PROFILE}') never loaded")
        default_data = self.profile_data[DEFAULT_PROFILE]
        ret_params  = default_data.get(section, {})
        if profile:
            if profile not in self.profile_data:
                raise RuntimeError(f"Profile '{profile}' never loaded")
            profile_data = self.profile_data[profile]
            profile_params = profile_data.get(section, {})
            ret_params.update(profile_params)
        return ret_params

#########################
# Trace logging support #
#########################

# from https://stackoverflow.com/questions/2183233/

TRACE = logging.DEBUG - 5
NOTICE = logging.WARNING + 5

class MyLogger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        logging.addLevelName(TRACE, "TRACE")
        logging.addLevelName(NOTICE, "NOTICE")

    def trace(self, msg, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)

    def notice(self, msg, *args, **kwargs):
        """Currently just write to default logging channel, later perhaps write to separate
        channel, or store in database
        """
        if self.isEnabledFor(NOTICE):
            #kwargs['stack_info'] = True
            self._log(NOTICE, msg, args, **kwargs)

logging.setLoggerClass(MyLogger)

########
# Misc #
########

def rankdata(a: Sequence[Number], method: str ='average', reverse: bool = True) -> list[Number]:
    """Standalone implementation of scipy.stats.rankdata, adapted from
    https://stackoverflow.com/a/3071441, with the following added:
      - `method` arg, with support for 'average' (default) and 'min'
      - `reverse` flag, with `True` (default) signifying descending sort order
        (i.e. the highest value in `a` has a rank of 1, as opposed to `len(a)`)

    Note that return rankings with be type `float` for method='average'
    and `int` for method='min'.
    """
    def rank_simple(vector):
        return sorted(range(len(vector)), key=vector.__getitem__, reverse=reverse)

    use_min  = method == 'min'
    n        = len(a)
    ivec     = rank_simple(a)
    svec     = [a[rank] for rank in ivec]
    sumranks = 0
    dupcount = 0
    minrank  = 0
    newarray = [0] * n
    for i in range(n):
        sumranks += i
        dupcount += 1
        minrank = minrank or i + 1
        if i == n - 1 or svec[i] != svec[i + 1]:
            averank = sumranks / float(dupcount) + 1
            for j in range(i - dupcount + 1, i + 1):
                newarray[ivec[j]] = minrank if use_min else averank
            sumranks = 0
            dupcount = 0
            minrank  = 0
    return newarray

def prettyprint(data, indent: int = 4, sort_keys: bool = True, noprint: bool = False) -> str:
    """Nicer version of pprint (which is actually kind of ugly)

    Note: assumes that input data can be dumped to json (typically a list or dict)
    """
    pattern = re.compile(r'^', re.MULTILINE)
    spaces = ' ' * indent
    data_json = json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
    pretty = re.sub(pattern, spaces, data_json)
    if not noprint:
        print(pretty)
    # no harm in always returning the formatted data (can be ignored by caller, if only
    # interested in printing)
    return pretty
