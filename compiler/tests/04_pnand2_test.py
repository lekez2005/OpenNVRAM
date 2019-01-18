#!/usr/bin/env python3
"""
Run regression tests on a parameterized nand 2.  This module doesn't
generate a multi_finger 2-input nand gate.  It generates only a minimum
size 2-input nand gate.
"""

from testutils import OpenRamTest
import debug


class Pnand2Test(OpenRamTest):

    def test_pnand2(self):
        from pgates import pnand2

        debug.info(2, "Checking 2-input nand gate")
        tx = pnand2.pnand2(size=1)
        self.local_check(tx)

    def test_bitcell_aligned_pnand2(self):
        from pgates import pnand2
        import tech
        debug.info(2, "Checking 1x size bitcell pitch matched")
        tech.drc_exceptions["pnand2"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tx = pnand2.pnand2(size=1, align_bitcell=True)
        self.local_drc_check(tx)


OpenRamTest.run_tests(__name__)
