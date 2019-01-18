#!/usr/bin/env python3
"""
Run regression tests on a parameterized nand 3.  This module doesn't
generate a multi_finger 3-input nand gate.  It generates only a minimum
size 3-input nand gate.
"""

from testutils import OpenRamTest
import debug


class Pnand2Test(OpenRamTest):

    def test_pnand3(self):
        from pgates import pnand3

        debug.info(2, "Checking 3-input nand gate")
        tx = pnand3.pnand3(size=1)
        self.local_check(tx)

    def test_bitcell_aligned_pnand3(self):
        from pgates import pnand3
        import tech

        debug.info(2, "Checking 3-input bitcell pitch matched nand gate")
        tech.drc_exceptions["pnand3"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tx = pnand3.pnand3(size=1, align_bitcell=True)
        self.local_drc_check(tx)


OpenRamTest.run_tests(__name__)
