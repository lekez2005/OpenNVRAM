#!/usr/bin/env python3
"""
Run a regression test on a pre2x4_horizontal .
"""

from test_base import TestBase
import debug


class Predecode2x4Test(TestBase):

    def test_predecode(self):
        from modules.push_rules.predecode2x4_horizontal import predecode2x4_horizontal

        debug.info(1, "Testing sample for hierarchy horizontal predecode2x4")

        a = predecode2x4_horizontal(use_flops=True)
        self.local_check(a)

    def test_negative_predecode(self):
        from modules.push_rules.predecode2x4_horizontal import predecode2x4_horizontal

        debug.info(1, "Testing sample for hierarchy horizontal predecode2x4")

        a = predecode2x4_horizontal(use_flops=True, negate=True)
        self.local_check(a)


Predecode2x4Test.run_tests(__name__)
