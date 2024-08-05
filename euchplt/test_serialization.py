#!/usr/bin/env python
# -*- coding: utf-8 -*-

import shelve

from euchplt.core import DataFile
from euchplt.tournament import Tournament

filename = 'test_serial.db'

tourn = Tournament.new("demo")

with shelve.open(DataFile(filename), flag='c') as db:
    db['tourn'] = tourn

with shelve.open(DataFile(filename)) as db:
    retrieve = {k: v for k, v in db.items()}

print(retrieve)
