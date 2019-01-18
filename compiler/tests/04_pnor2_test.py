#!/usr/bin/env python3
"""
Run regression tests on a parameterized nor 2.  This module doesn't
generate a multi_finger 2-input nor gate.  It generates only a minimum
size 2-input nor gate.
"""

from testutils import OpenRamTest
import debug


class Pnor2Test(OpenRamTest):

    def runTest(self):
        from pgates import pnor2

        debug.info(2, "Checking 2-input nor gate")
        tx = pnor2.pnor2(size=1)
        self.local_check(tx)

        
OpenRamTest.run_tests(__name__)
