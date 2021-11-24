# -*- coding: utf-8 -*-

from os import environ
import os.path
import logging
import logging.handlers
import random

from . import utils

######################
# Config/Environment #
######################

FILE_DIR      = os.path.dirname(os.path.realpath(__file__))
BASE_DIR      = os.path.realpath(os.path.join(FILE_DIR, os.pardir))
CONFIG_DIR    = 'config'
CONFIG_FILE   = 'config.yml'
CONFIG_PATH   = os.path.join(BASE_DIR, CONFIG_DIR, CONFIG_FILE)
cfg           = utils.Config(CONFIG_PATH)

param         = cfg.config('params')
env_param     = {'EUCHPLTDEBUG': 'debug'}
param.update({v: environ[k] for k, v in env_param.items() if k in environ})

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

##############
# Exceptions #
##############

class LogicError(RuntimeError):
    pass

class ImplementationError(RuntimeError):
    pass

##################
# Basedata Setup #
##################

# LATER: only use configured value if debug/dev mode!!!
#random.seed(param.get('random_seed'))

def validate_basedata(basedata, offset = 0) -> None:
    """Make sure that the embedded index for base data elements matches the position
    within the data structure

    :return: void (failed assert on validation error)
    """
    for elem in basedata:
        assert elem.idx == basedata.index(elem) + offset
