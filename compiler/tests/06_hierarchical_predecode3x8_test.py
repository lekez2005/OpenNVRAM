#!/usr/bin/env python3
"""
Run a regression test on a hierarchical_predecode3x8.
"""

from testutils import OpenRamTest
import debug


class HierarchicalPredecode3x8Test(OpenRamTest):

    def runTest(self):
        from modules import hierarchical_predecode3x8 as pre

        debug.info(1, "Testing sample for hierarchy_predecode3x8")
        a = pre.hierarchical_predecode3x8()
        self.local_drc_check(a)


OpenRamTest.run_tests(__name__)
