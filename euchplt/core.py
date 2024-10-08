# -*- coding: utf-8 -*-

import re
from os import environ, rename
import os.path
from datetime import datetime
import logging
import logging.handlers

from . import utils

######################
# Config/Environment #
######################

DFLT_CONFIG_FILES = ['base_config.yml',
                     'players_teams.yml',
                     'strategies.yml',
                     'tournaments.yml']

FILE_DIR     = os.path.dirname(os.path.realpath(__file__))
BASE_DIR     = os.path.realpath(os.path.join(FILE_DIR, os.pardir))
CONFIG_DIR   = environ.get('EUCH_CONFIG_DIR') or os.path.join(BASE_DIR, 'config')
CONFIG_FILES = environ.get('EUCH_CONFIG_FILES') or DFLT_CONFIG_FILES
cfg          = utils.Config(CONFIG_FILES, CONFIG_DIR)

DEBUG        = int(environ.get('EUCH_DEBUG') or 0)

########
# Data #
########

DATA_DIR    = 'data'
DATA_TS_FMT = '%Y%m%d_%H%M%S'

def DataFile(file_name: str, dir: str = DATA_DIR, add_ts: bool = False) -> str:
    """Given name of file, return full path name (in DATA_DIR, or specified directory).
    If add_ts is specified, the current timestamp will be inserted at the end of the
    filename (before the filetype suffix).
    """
    if add_ts:
        now_ts = datetime.now().strftime(DATA_TS_FMT)
        file_name = re.sub(r'(\.[a-z]+)$', f'-{now_ts}\\1', file_name)
    return os.path.join(BASE_DIR, dir, file_name)

def ArchiveDataFile(file_name: str) -> None:
    """Rename data file to "archived" version (current datetime appended),
    which also has the effect of removing it from the file system, so that
    a new version can be created
    """
    data_file = DataFile(file_name)
    arch_ts = datetime.now().strftime(DATA_TS_FMT)
    try:
        rename(data_file, data_file + '-' + arch_ts)
    except FileNotFoundError:
        pass

###########
# Logging #
###########

# create logger (TODO: logging parameters belong in config file as well!!!)
LOGGER_NAME  = environ.get('EUCH_LOG_NAME') or 'euchplt'
LOG_DIR      = 'log'
LOG_FILE     = LOGGER_NAME + '.log'
LOG_PATH     = os.path.join(BASE_DIR, LOG_DIR, LOG_FILE)
LOG_FMTR     = logging.Formatter('%(asctime)s %(levelname)s [%(filename)s:%(lineno)s]: %(message)s')
LOG_FILE_MAX = 25000000
LOG_FILE_NUM = 50

dflt_hand = logging.handlers.RotatingFileHandler(LOG_PATH, 'a', LOG_FILE_MAX, LOG_FILE_NUM)
dflt_hand.setLevel(logging.DEBUG)
dflt_hand.setFormatter(LOG_FMTR)

dbg_hand = logging.StreamHandler()
dbg_hand.setLevel(logging.DEBUG)
dbg_hand.setFormatter(LOG_FMTR)

log = logging.getLogger(LOGGER_NAME)
log.setLevel(logging.INFO)
log.addHandler(dflt_hand)
if DEBUG:
    log.setLevel(logging.DEBUG)
    if DEBUG > 1:
        log.addHandler(dbg_hand)

##############
# Exceptions #
##############

class ConfigError(RuntimeError):
    """
    """
    pass

class LogicError(RuntimeError):
    """
    """
    pass

class ImplementationError(RuntimeError):
    """
    """
    pass

##################
# Basedata Setup #
##################

def validate_basedata(basedata, offset: int = 0) -> None:
    """Make sure that the embedded index for base data elements matches the position
    within the data structure (failed assert on validation error)
    """
    for elem in basedata:
        assert elem.idx == basedata.index(elem) + offset
