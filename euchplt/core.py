# -*- coding: utf-8 -*-

from os import environ
import os.path
import logging
import logging.handlers

from . import utils

######################
# Config/Environment #
######################

FILE_DIR      = os.path.dirname(os.path.realpath(__file__))
BASE_DIR      = os.path.realpath(os.path.join(FILE_DIR, os.pardir))
CONFIG_DIR    = 'config'
CONFIG_FILE   = environ.get('EUCHPLT_CONFIG_FILE') or 'config.yml'
CONFIG_PATH   = os.path.join(BASE_DIR, CONFIG_DIR, CONFIG_FILE)
cfg           = utils.Config(CONFIG_PATH)

###########
# Logging #
###########

# create logger (TODO: logging parameters belong in config file as well!!!)
LOGGER_NAME  = 'euchplt'
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
if environ.get('EUCHPLT_DEBUG'):
    log.setLevel(logging.DEBUG)
    log.addHandler(dbg_hand)

##############
# Exceptions #
##############

class ConfigError(RuntimeError):
    pass

class LogicError(RuntimeError):
    pass

class ImplementationError(RuntimeError):
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
