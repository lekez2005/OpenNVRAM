#!/usr/bin/env python3
"""
Run a regression test on a pre2x4_horizontal .
"""

from test_base import TestBase
import debug


class Predecode3x8Test(TestBase):

    def test_predecode(self):
        from modules.push_rules.predecode3x8_horizontal import predecode3x8_horizontal

        debug.info(1, "Testing sample for hierarchy horizontal predecode3x8")

        a = predecode3x8_horizontal(use_flops=True)
        self.local_check(a)

    def test_negative_predecode(self):
        from modules.push_rules.predecode3x8_horizontal import predecode3x8_horizontal

        debug.info(1, "Testing sample for hierarchy horizontal predecode3x8")

        a = predecode3x8_horizontal(use_flops=True, negate=True)
        self.local_check(a)


Predecode3x8Test.run_tests(__name__)
