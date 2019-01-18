#!/usr/bin/env python3

import os
import re
import sys
import unittest

sys.path.append(os.path.join(sys.path[0],".."))
sys.path.append(os.path.join(sys.path[0],"../.."))
import globals

(OPTS, args) = globals.parse_args()
del sys.argv[1:]

from tests.testutils import header
header(__file__, OPTS.tech_name)

# get a list of all files in the tests directory
files = os.listdir(sys.path[0])

# assume any file that ends in "test.py" in it is a regression test
nametest = re.compile(r"test\.py$", re.IGNORECASE)
tests = list(filter(nametest.search, files))
tests.sort()

# import all of the modules
filenameToModuleName = lambda f: os.path.splitext(f)[0]
moduleNames = list(map(filenameToModuleName, tests))
modules = list(map(__import__, moduleNames))
suite = unittest.TestSuite()
load = unittest.defaultTestLoader.loadTestsFromModule
suite.addTests(list(map(load, modules)))
unittest.TextTestRunner(verbosity=2).run(suite)
