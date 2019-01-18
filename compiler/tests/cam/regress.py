#!/usr/bin/env python3
import os
import re
import sys

import unittest

from cam_test_base import header
import globals
(OPTS, args) = globals.parse_args()
del sys.argv[1:]
header(__file__, OPTS.tech_name)


# get a list of all files in the tests directory
files = os.listdir(os.path.abspath(os.path.dirname(__file__)))

nametest = re.compile(r"^[0-2]?[0-9].*test\.py$", re.IGNORECASE)
tests = list(filter(nametest.search, files))
tests.sort()

# import all of the modules
moduleNames = list(map(lambda f: os.path.splitext(f)[0], tests))
modules = list(map(__import__, moduleNames))
suite = unittest.TestSuite()
load = unittest.defaultTestLoader.loadTestsFromModule
suite.addTests(list(map(load, modules)))
unittest.TextTestRunner(verbosity=2, failfast=False).run(suite)
