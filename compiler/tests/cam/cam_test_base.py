import os
import sys

module_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.abspath(os.path.join(module_dir, "../../")))

import unittest
from tests.testutils import header

import globals
from globals import OPTS

from tests.testutils import openram_test


class CamTestBase(openram_test):
    @classmethod
    def setUpClass(cls):
        super(CamTestBase, cls).setUpClass()
        globals.init_openram("config_cam_{}".format(OPTS.tech_name))
        OPTS.check_lvsdrc = False

    def setUp(self):
        self.reset()

    @classmethod
    def tearDownClass(cls):
        super(CamTestBase, cls).tearDownClass()
        globals.end_openram()


def run_tests(name):
    # instantiate a copy of the class to actually run the test
    if name == "__main__":
        (OPTS, args) = globals.parse_args()
        del sys.argv[1:]
        header(__file__, OPTS.tech_name)
        unittest.main()

