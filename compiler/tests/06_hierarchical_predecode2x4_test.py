#!/usr/bin/env python3
"""
Run a regression test on a hierarchical_predecode2x4.
"""

from testutils import OpenRamTest
import debug


class HierarchicalPredecode2x4Test(OpenRamTest):

    def runTest(self):
        from modules import hierarchical_predecode2x4 as pre

        debug.info(1, "Testing sample for hierarchy_predecode2x4")
        a = pre.hierarchical_predecode2x4()
        self.local_drc_check(a)

        
OpenRamTest.run_tests(__name__)
