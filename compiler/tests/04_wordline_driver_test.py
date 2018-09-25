#!/usr/bin/env python2.7
"""
Run a regresion test on a wordline_driver array
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug



class wordline_driver_test(openram_test):

    @classmethod
    def setUpClass(cls):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

    @classmethod
    def tearDownClass(cls):
        globals.end_openram()

    def run_commands(self, rows, cols):

        global verify
        import verify
        OPTS.check_lvsdrc = False

        import wordline_driver

        tx = wordline_driver.wordline_driver(rows=rows, no_cols=cols)
        self.local_check(tx)

    # @unittest.skip("SKIPPING 04_driver_test")
    def test_no_buffer(self):
        debug.info(1, "Checking driver without buffer")
        self.run_commands(8, 8)

    def test_with_buffer(self):
        debug.info(1, "Checking driver with buffer")
        self.run_commands(8, 32)

        
# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
