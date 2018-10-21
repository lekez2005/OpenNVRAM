#!/usr/bin/env python2.7
"""
Run regresion tests on a parameterized pnand3.
This module doesn't generate a multi-finger 3-input nand gate.
It generates only a minimum size 3-input nand gate.
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class pnand3_test(openram_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        global verify
        import verify
        OPTS.check_lvsdrc = False

        import pnand3
        import tech

        debug.info(2, "Checking 3-input nand gate")
        tx = pnand3.pnand3(size=1)
        self.local_check(tx)

        debug.info(2, "Checking 3-input bitcell pitch matched nand gate")
        tech.drc_exceptions["pnand3"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tx = pnand3.pnand3(size=1, align_bitcell=True)
        self.local_drc_check(tx)

        OPTS.check_lvsdrc = True
        globals.end_openram()
        

# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
