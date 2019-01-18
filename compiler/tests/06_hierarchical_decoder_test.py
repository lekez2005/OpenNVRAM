#!/usr/bin/env python3
"""
Run a regression test on a hierarchical_decoder.
"""

from testutils import OpenRamTest
import debug


class HierarchicalDecoderTest(OpenRamTest):

    def runTest(self):
        from modules import hierarchical_decoder
        import tech

        tech.drc_exceptions["hierarchical_decoder"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]

        debug.info(1, "Testing 16 row sample for hierarchical_decoder")
        a = hierarchical_decoder.hierarchical_decoder(rows=16)
        self.local_drc_check(a)

        debug.info(1, "Testing 32 row sample for hierarchical_decoder")
        a = hierarchical_decoder.hierarchical_decoder(rows=32)
        self.local_drc_check(a)

        debug.info(1, "Testing 128 row sample for hierarchical_decoder")
        a = hierarchical_decoder.hierarchical_decoder(rows=128)
        self.local_drc_check(a)

        debug.info(1, "Testing 512 row sample for hierarchical_decoder")
        a = hierarchical_decoder.hierarchical_decoder(rows=512)
        self.local_drc_check(a)


OpenRamTest.run_tests(__name__)
