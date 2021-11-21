# -*- coding: utf-8 -*-

import logging
import json
import re

import yaml

#####################
# Config Management #
#####################

class Config(object):
    """Manages YAML config information, features include:
      - Caching by config file
      - Fetching by section
      - Overlays on 'default' profile
    """
    cfg_profiles = dict()  # {config_file: {profile_name: {section_name: ...}}}

    def __init__(self, path):
        """
        :param path: path to YAML config file
        """
        self.path = path
        if Config.cfg_profiles.get(self.path) is None:
            Config.cfg_profiles[self.path] = {}

    def config(self, section, profile = None):
        """Get config section for specified profile

        :param section: section within profile (or 'default')
        :param profile: [optional] if specified, overlay entries on top of 'default' profile
        :return: dict indexed by key
        """
        if profile in Config.cfg_profiles[self.path]:
            return Config.cfg_profiles[self.path][profile].get(section, {})

        with open(self.path, 'r') as f:
            cfg = yaml.safe_load(f)
        if cfg:
            prof_data = cfg.get('default', {})
            if profile:
                prof_data.update(cfg.get(profile, {}))
            Config.cfg_profiles[self.path][profile] = prof_data
        else:
            Config.cfg_profiles[self.path][profile] = {}

        return Config.cfg_profiles[self.path][profile].get(section, {})

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

def prettyprint(data, indent = 4, sort_keys = True, noprint = False):
    """Nicer version of pprint (which is actually kind of ugly)

    Note: assumes that input data can be dumped to json (typically a list or dict)
    """
    pattern = re.compile(r'^', re.MULTILINE)
    spaces = ' ' * indent
    if noprint:
        return re.sub(pattern, spaces, json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False))
    else:
        print(re.sub(pattern, spaces, json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)))
