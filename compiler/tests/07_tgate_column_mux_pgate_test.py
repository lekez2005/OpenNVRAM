#!/usr/bin/env python3
"""
Run a regression test on a single transistor column_mux.
"""

from testutils import OpenRamTest


class TgateColMuxPgateTest(OpenRamTest):

    def runTest(self):
        from modules.tgate_column_mux_pgate import tgate_column_mux_pgate
        from globals import OPTS
        self.debug.info(1, "8x ptx tgate column mux")

        OPTS.tgate_size = 8
        a = tgate_column_mux_pgate()
        self.local_check(a)


OpenRamTest.run_tests(__name__)
