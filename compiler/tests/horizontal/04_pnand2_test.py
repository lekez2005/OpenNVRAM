#!/usr/bin/env python3
"""
Run regression tests on a parameterized horizontal nand2
"""
from test_base import TestBase


class Pnand2Test(TestBase):

    def test_size_1(self):
        import debug
        from modules.horizontal.pnand2_horizontal import pnand2_horizontal

        debug.info(2, "Checking 1x size horizontal nand2")
        dut = pnand2_horizontal(size=1)
        self.add_body_tap_and_test(dut)

    def test_size_2(self):
        import debug
        from modules.horizontal.pnand2_horizontal import pnand2_horizontal

        debug.info(2, "Checking two-finger horizontal nand2")
        dut = pnand2_horizontal(size=2)
        self.add_body_tap_and_test(dut)


Pnand2Test.run_tests(__name__)
