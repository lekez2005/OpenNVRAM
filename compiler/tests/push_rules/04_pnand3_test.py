#!/usr/bin/env python3
"""
Run regression tests on a parameterized horizontal nand3
"""
from test_base import TestBase


class Pnand3Test(TestBase):

    def test_size_1(self):
        import debug
        from modules.push_rules.pnand3_horizontal import pnand3_horizontal

        debug.info(2, "Checking 1x size horizontal nand3")
        dut = pnand3_horizontal(size=1)
        self.add_body_tap_and_test(dut)

    def test_size_2(self):
        import debug
        from modules.push_rules.pnand3_horizontal import pnand3_horizontal

        debug.info(2, "Checking two-finger horizontal nand2")
        dut = pnand3_horizontal(size=2)
        self.add_body_tap_and_test(dut)


Pnand3Test.run_tests(__name__)
